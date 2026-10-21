
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.html import strip_tags
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions
from .models import Categoria, Archivo, Publicacion, GaleriaPublicacion
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from .models import Perfil
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import user_passes_test
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, UnidentifiedImageError
from django.views.decorators.http import require_POST
from .models import Comentario
from django.shortcuts import get_object_or_404

import os
import uuid
import nh3

# VERIFICAR SI EL USUARIO ES ADMINISTRADOR

def es_administrador(user):

    return (

        user.is_authenticated

        and user.is_active

        and user.is_superuser

    )

# Create your views here.
def index(request):

    # Obtener únicamente las noticias publicadas
    publicaciones = Publicacion.objects.filter(
        estado=Publicacion.ESTADO_PUBLICADO
    ).select_related(
        'categoria',
        'imagen_portada'
    ).order_by('-createdat')

    # Últimas 3 noticias para el carrusel
    noticias_destacadas = publicaciones[:3]

    # Últimas 6 noticias para las tarjetas
    noticias_recientes = publicaciones[:6]

    return render(
        request,
        'home/index.html',
        {
            'noticias_destacadas': noticias_destacadas,
            'noticias_recientes': noticias_recientes
        }
    )

def contactanos(request):
    return render(request, 'home/contactanos.html')

def base(request):
    return render(request, 'home/base.html')

def categoria(request, pk=None):

    categorias = Categoria.objects.all().order_by('nombre')

    categoria_actual = get_object_or_404(
        Categoria,
        pk=pk
    ) if pk else None

    publicaciones = Publicacion.objects.filter(
        estado=Publicacion.ESTADO_PUBLICADO
    ).select_related(
        'categoria',
        'autor',
        'imagen_portada'
    )

    if categoria_actual:
        publicaciones = publicaciones.filter(
            categoria=categoria_actual
        )

    return render(
        request,
        'home/categoria.html',
        {
            'categorias': categorias,
            'categoria_actual': categoria_actual,
            'publicaciones': publicaciones.order_by('-createdat')
        }
    )

def noticia(request, pk=None):

    # Si no se proporciona una noticia, buscar una publicada
    if pk is None:

        publicacion = Publicacion.objects.filter(
            estado=Publicacion.ESTADO_PUBLICADO
        ).order_by('-createdat').first()

        if publicacion is None:
            messages.info(
                request,
                'Todavía no hay noticias publicadas.'
            )
            return redirect('home:index')

        return redirect('home:noticia_detalle', pk=publicacion.pk)

    # Buscar la noticia correspondiente
    publicacion = get_object_or_404(
        Publicacion,
        pk=pk,
        estado=Publicacion.ESTADO_PUBLICADO
    )

    # Registrar comentario
    if request.method == 'POST':

        if not request.user.is_authenticated:
            messages.error(
                request,
                'Debes iniciar sesión para comentar.'
            )
            return redirect('home:login')

        contenido = request.POST.get('contenido', '').strip()

        if contenido:

            Comentario.objects.create(
                publicacion=publicacion,
                user=request.user,
                contenido=contenido,
                estado=Comentario.ESTADO_PENDIENTE
            )

            messages.success(
                request,
                'Tu comentario fue enviado y está pendiente de aprobación.'
            )

            return redirect(
                'home:noticia_detalle',
                pk=publicacion.pk
            )

        messages.error(
            request,
            'El comentario no puede estar vacío.'
        )

    # Consultar comentarios aprobados
    comentarios = Comentario.objects.filter(
        publicacion=publicacion,
        estado=Comentario.ESTADO_APROBADO
    ).select_related('user').order_by('-createdat')

    return render(
        request,
        'home/noticia.html',
        {
            'publicacion': publicacion,
            'comentarios': comentarios
        }
    )

@login_required
def perfil(request):

    usuario = request.user

    perfil_usuario, _ = Perfil.objects.get_or_create(
        user=usuario
    )

    return render(
        request,
        'home/perfil.html',
        {
            'usuario': usuario,
            'perfil_usuario': perfil_usuario
        }
    )

def sign_up(request):

    if request.method == 'POST':

        # Obtener datos del formulario
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        apellido_paterno = request.POST.get('apellido_paterno', '').strip()
        apellido_materno = request.POST.get('apellido_materno', '').strip()

        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        # Validar campos obligatorios
        if not username or not email or not password1 or not password2:
            messages.error(
                request,
                'Debes completar todos los campos obligatorios.'
            )
            return render(request, 'home/sign_up.html')

        # Validar nombre de usuario
        if User.objects.filter(username__iexact=username).exists():
            messages.error(
                request,
                'Este nombre de usuario ya está registrado.'
            )
            return render(request, 'home/sign_up.html')

        # Validar correo electrónico
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Ingresa un correo electrónico válido.')
            return render(request, 'home/sign_up.html', {
                'datos': request.POST
            })

        if User.objects.filter(email__iexact=email).exists():
            messages.error(
                request,
                'Este correo electrónico ya está registrado.'
            )
            return render(request, 'home/sign_up.html', {
                'datos': request.POST
            })

        # Verificar contraseñas
        if password1 != password2:
            messages.error(
                request,
                'Las contraseñas no coinciden.'
            )
            return render(request, 'home/sign_up.html', {
                'datos': request.POST
            })

        # Validar seguridad de la contraseña
        try:
            validate_password(password1)
        except ValidationError as error:
            for mensaje in error.messages:
                messages.error(request, mensaje)

            return render(request, 'home/sign_up.html', {
                'datos': request.POST
            })

        # Crear usuario y actualizar perfil
        try:
            with transaction.atomic():

                usuario = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password1,
                    first_name=first_name
                )

                # Signals crea el perfil automáticamente
                perfil, _ = Perfil.objects.get_or_create(
                    user=usuario
                )

                perfil.apellido_paterno = apellido_paterno
                perfil.apellido_materno = apellido_materno
                perfil.save()

        except Exception:
            messages.error(
                request,
                'No fue posible crear la cuenta. Inténtalo nuevamente.'
            )
            return render(request, 'home/sign_up.html', {
                'datos': request.POST
            })

        messages.success(
            request,
            'Tu cuenta se creó correctamente. Ahora puedes iniciar sesión.'
        )

        return redirect('home:login')

    return render(request, 'home/sign_up.html', {
        'datos': request.POST
    })

def validar_imagen(imagen):
    extensiones_permitidas = {'.jpg', '.jpeg', '.png', '.webp'}
    tipos_permitidos = {
        'image/jpeg',
        'image/png',
        'image/webp'
    }

    extension = os.path.splitext(imagen.name)[1].lower()

    # Validar extensión
    if extension not in extensiones_permitidas:
        raise ValidationError(
            'Solo se permiten imágenes JPG, PNG o WEBP.'
        )

    # Validar tamaño máximo: 5 MB
    if imagen.size > 5 * 1024 * 1024:
        raise ValidationError(
            'Cada imagen debe pesar menos de 5 MB.'
        )

    # Validar el contenido real del archivo
    try:
        from PIL import Image, UnidentifiedImageError

        imagen.seek(0)

        with Image.open(imagen) as img:
            formato = img.format
            img.verify()

        if formato not in {'JPEG', 'PNG', 'WEBP'}:
            raise ValidationError(
                'El archivo no tiene un formato de imagen permitido.'
            )

    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError(
            'El archivo seleccionado no es una imagen válida.'
        )

    finally:
        imagen.seek(0)

    # Validar tipo MIME declarado
    if imagen.content_type not in tipos_permitidos:
        raise ValidationError(
            'El tipo de archivo no está permitido.'
        )

def guardar_archivo(imagen, usuario):

    nombre_original = imagen.name

    extension = os.path.splitext(nombre_original)[1].lower()

    nombre_unico = f'{uuid.uuid4().hex}{extension}'

    imagen.name = nombre_unico

    archivo = Archivo.objects.create(
        nombre=nombre_original,
        nombre_temporal=nombre_unico,
        ruta=imagen,
        tipo=imagen.content_type,
        tamano=imagen.size,
        fk_user=usuario
    )

    return archivo

@staff_member_required
def crear_publicacion(request):

    # Obtener categorías desde PostgreSQL
    categorias = Categoria.objects.all().order_by('nombre')

    if request.method == 'POST':

        # Obtener datos del formulario
        titulo = request.POST.get('titulo', '').strip()
        resumen = request.POST.get('resumen', '').strip()
        contenido_original = request.POST.get('contenido', '')
        categoria_id = request.POST.get('categoria', '')
        estado = request.POST.get('estado', 'borrador')

        # Obtener imágenes
        imagen_portada = request.FILES.get('imagen_portada')
        imagenes_galeria = request.FILES.getlist('galeria')

        # Limpiar HTML generado por Quill
        contenido = nh3.clean(
            contenido_original,
            tags={
                'p', 'br', 'strong', 'em', 'u', 's',
                'h1', 'h2', 'h3',
                'ol', 'ul', 'li',
                'a', 'blockquote', 'span'
            },
            attributes={
                'a': {'href', 'title'},
                'span': {'class'},
                'p': {'class'},
            }
        )

        # Validar campos obligatorios
        if not titulo or not resumen or not strip_tags(contenido).strip():

            messages.error(
                request,
                'Debes completar el título, resumen y contenido.'
            )

            return render(
                request,
                'home/crear_publicacion.html',
                {'categorias': categorias}
            )

        # Validar estado
        if estado not in ['borrador', 'publicado']:
            estado = 'borrador'

        # Buscar categoría
        categoria = None

        if categoria_id:

            try:
                categoria = Categoria.objects.get(pk=categoria_id)

            except (Categoria.DoesNotExist, ValueError, TypeError):

                messages.error(
                    request,
                    'La categoría seleccionada no es válida.'
                )

                return render(
                    request,
                    'home/crear_publicacion.html',
                    {'categorias': categorias}
                )

        # Validar todas las imágenes antes de guardar
        try:

            if imagen_portada:
                validar_imagen(imagen_portada)

            for imagen in imagenes_galeria:
                validar_imagen(imagen)

        except ValidationError as error:

            messages.error(
                request,
                ' '.join(error.messages)
            )

            return render(
                request,
                'home/crear_publicacion.html',
                {'categorias': categorias}
            )

        # Guardar los registros en PostgreSQL
        try:

            with transaction.atomic():

                # Guardar imagen de portada
                archivo_portada = None

                if imagen_portada:
                    archivo_portada = guardar_archivo(
                        imagen_portada,
                        request.user
                    )

                # Crear publicación
                publicacion = Publicacion.objects.create(
                    titulo=titulo,
                    resumen=resumen,
                    contenido=contenido,
                    categoria=categoria,
                    autor=request.user,
                    estado=estado,
                    imagen_portada=archivo_portada
                )

                # Guardar imágenes de galería
                for imagen in imagenes_galeria:

                    archivo = guardar_archivo(
                        imagen,
                        request.user
                    )

                    GaleriaPublicacion.objects.create(
                        publicacion=publicacion,
                        archivo=archivo
                    )

        except Exception:
            messages.error(
                request,
                'Ocurrió un error al guardar la publicación.'
            )

            return render(
                request,
                'home/crear_publicacion.html',
                {'categorias': categorias}
            )

        messages.success(
            request,
            'La publicación y sus imágenes se guardaron correctamente.'
        )

        return redirect('home:crudNoticias')

    return render(
        request,
        'home/crear_publicacion.html',
        {'categorias': categorias}
    )

@user_passes_test(es_administrador)
def crear_usuario(request):

    if request.method == 'POST':

        # OBTENER DATOS DEL FORMULARIO
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()

        apellido_paterno = request.POST.get('apellido_paterno', '').strip()
        apellido_materno = request.POST.get('apellido_materno', '').strip()

        rol = request.POST.get('rol', 'colaborador')

        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        # CONSERVAR DATOS SI HAY ERRORES
        contexto = {
            'datos': request.POST
        }

        # VALIDAR CAMPOS OBLIGATORIOS
        if not username or not email or not password1 or not password2:

            messages.error(
                request,
                'Debes completar todos los campos obligatorios.'
            )

            return render(
                request,
                'home/crear_usuario.html',
                contexto
            )

        # VALIDAR USUARIO DUPLICADO
        if User.objects.filter(username__iexact=username).exists():

            messages.error(
                request,
                'Este nombre de usuario ya está registrado.'
            )

            return render(
                request,
                'home/crear_usuario.html',
                contexto
            )

        # VALIDAR CORREO
        try:
            validate_email(email)

        except ValidationError:

            messages.error(
                request,
                'Introduce un correo electrónico válido.'
            )

            return render(
                request,
                'home/crear_usuario.html',
                contexto
            )

        # VALIDAR CORREO DUPLICADO
        if User.objects.filter(email__iexact=email).exists():

            messages.error(
                request,
                'Este correo electrónico ya está registrado.'
            )

            return render(
                request,
                'home/crear_usuario.html',
                contexto
            )

        # VALIDAR ROL
        if rol not in ['colaborador', 'editor', 'administrador']:

            messages.error(
                request,
                'Selecciona un rol válido.'
            )

            return render(
                request,
                'home/crear_usuario.html',
                contexto
            )

        # VERIFICAR CONTRASEÑAS
        if password1 != password2:

            messages.error(
                request,
                'Las contraseñas no coinciden.'
            )

            return render(
                request,
                'home/crear_usuario.html',
                contexto
            )

        # VALIDAR SEGURIDAD
        try:

            usuario_temporal = User(
                username=username,
                email=email,
                first_name=first_name
            )

            validate_password(
                password1,
                user=usuario_temporal
            )

        except ValidationError as errores:

            for error in errores.messages:
                messages.error(request, error)

            return render(
                request,
                'home/crear_usuario.html',
                contexto
            )

        # CONFIGURAR PERMISOS SEGÚN EL ROL
        es_staff = rol in ['editor', 'administrador']
        es_superuser = rol == 'administrador'

        # GUARDAR EN POSTGRESQL
        try:

            with transaction.atomic():

                usuario = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password1,
                    first_name=first_name,
                    is_staff=es_staff,
                    is_superuser=es_superuser
                )

                # EL SIGNAL CREA EL PERFIL AUTOMÁTICAMENTE
                perfil, _ = Perfil.objects.get_or_create(
                    user=usuario
                )

                perfil.apellido_paterno = apellido_paterno
                perfil.apellido_materno = apellido_materno

                perfil.save()

        except Exception:

            messages.error(
                request,
                'Ocurrió un error al crear el usuario.'
            )

            return render(
                request,
                'home/crear_usuario.html',
                contexto
            )

        messages.success(
            request,
            'El usuario se creó correctamente.'
        )

        return redirect('home:crudUsuarios')

    return render(
        request,
        'home/crear_usuario.html'
    )

@user_passes_test(es_administrador)
def editar_usuario(request, usuario_id):

    usuario = User.objects.get(pk=usuario_id)
    perfil, _ = Perfil.objects.get_or_create(user=usuario)

    if request.method == 'POST':

        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        apellido_paterno = request.POST.get('apellido_paterno', '').strip()
        apellido_materno = request.POST.get('apellido_materno', '').strip()
        rol = request.POST.get('rol', 'colaborador')

        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        contexto = {
            'usuario_editado': usuario,
            'perfil_editado': perfil,
            'datos': request.POST
        }

        if not username or not email:
            messages.error(request, 'El usuario y el correo son obligatorios.')
            return render(request, 'home/crear_usuario.html', contexto)

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Introduce un correo válido.')
            return render(request, 'home/crear_usuario.html', contexto)

        if User.objects.filter(username__iexact=username).exclude(pk=usuario.pk).exists():
            messages.error(request, 'El nombre de usuario ya está registrado.')
            return render(request, 'home/crear_usuario.html', contexto)

        if User.objects.filter(email__iexact=email).exclude(pk=usuario.pk).exists():
            messages.error(request, 'El correo ya está registrado.')
            return render(request, 'home/crear_usuario.html', contexto)

        if rol not in ['colaborador', 'editor', 'administrador']:
            messages.error(request, 'Selecciona un rol válido.')
            return render(request, 'home/crear_usuario.html', contexto)

        if usuario.pk == request.user.pk and rol != 'administrador':
            messages.error(request, 'No puedes quitarte tu propio rol de administrador.')
            return render(request, 'home/crear_usuario.html', contexto)

        if password1 or password2:

            if password1 != password2:
                messages.error(request, 'Las contraseñas no coinciden.')
                return render(request, 'home/crear_usuario.html', contexto)

            try:
                validate_password(password1, user=usuario)
            except ValidationError as errores:
                for error in errores.messages:
                    messages.error(request, error)
                return render(request, 'home/crear_usuario.html', contexto)

        with transaction.atomic():

            usuario.username = username
            usuario.email = email
            usuario.first_name = first_name

            usuario.is_staff = rol in ['editor', 'administrador']
            usuario.is_superuser = rol == 'administrador'

            if password1:
                usuario.set_password(password1)

            usuario.save()

            perfil.apellido_paterno = apellido_paterno
            perfil.apellido_materno = apellido_materno
            perfil.save()

        if usuario.pk == request.user.pk and password1:
            update_session_auth_hash(request, usuario)

        messages.success(request, 'El usuario se actualizó correctamente.')

        return redirect('home:crudUsuarios')

    return render(
        request,
        'home/crear_usuario.html',
        {
            'usuario_editado': usuario,
            'perfil_editado': perfil
        }
    )

@user_passes_test(es_administrador)
def cambiar_estado_usuario(request, usuario_id):

    # Solo permitir solicitudes POST
    if request.method != 'POST':
        messages.error(
            request,
            'No se permite realizar esta acción.'
        )
        return redirect('home:crudUsuarios')

    # Buscar usuario
    usuario = get_object_or_404(User, pk=usuario_id)

    # Evitar que el administrador se bloquee a sí mismo
    if usuario.pk == request.user.pk:
        messages.error(
            request,
            'No puedes bloquear tu propia cuenta.'
        )
        return redirect('home:crudUsuarios')

    # Proteger otras cuentas de administrador
    if usuario.is_superuser:
        messages.error(
            request,
            'No puedes cambiar el estado de otro administrador desde esta opción.'
        )
        return redirect('home:crudUsuarios')

    # Cambiar estado
    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=['is_active'])

    if usuario.is_active:
        messages.success(
            request,
            f'El usuario {usuario.username} fue desbloqueado correctamente.'
        )
    else:
        messages.success(
            request,
            f'El usuario {usuario.username} fue bloqueado correctamente.'
        )

    return redirect('home:crudUsuarios')

@login_required
def crud_cambiar_contrasena(request):

    usuario = request.user

    if request.method == 'POST':

        password_actual = request.POST.get('password_actual', '')
        password_nueva = request.POST.get('password_nueva', '')
        confirmar_password = request.POST.get('confirmar_password', '')

        # VALIDAR CAMPOS OBLIGATORIOS
        if not password_actual or not password_nueva or not confirmar_password:

            messages.error(
                request,
                'Todos los campos son obligatorios.'
            )

            return redirect('home:crudCambiarContrasena')

        # VERIFICAR CONTRASEÑA ACTUAL
        if not usuario.check_password(password_actual):

            messages.error(
                request,
                'La contraseña actual es incorrecta.'
            )

            return redirect('home:crudCambiarContrasena')

        # VERIFICAR QUE LAS CONTRASEÑAS COINCIDAN
        if password_nueva != confirmar_password:

            messages.error(
                request,
                'Las contraseñas nuevas no coinciden.'
            )

            return redirect('home:crudCambiarContrasena')

        # EVITAR UTILIZAR LA MISMA CONTRASEÑA
        if usuario.check_password(password_nueva):

            messages.error(
                request,
                'La nueva contraseña debe ser diferente a la actual.'
            )

            return redirect('home:crudCambiarContrasena')

        # VALIDAR SEGURIDAD DE LA CONTRASEÑA
        try:

            validate_password(password_nueva, user=usuario)

        except ValidationError as errores:

            for error in errores.messages:
                messages.error(request, error)

            return redirect('home:crudCambiarContrasena')

        # ACTUALIZAR CONTRASEÑA
        usuario.set_password(password_nueva)
        usuario.save(update_fields=['password'])

        # MANTENER LA SESIÓN INICIADA
        update_session_auth_hash(request, usuario)

        messages.success(
            request,
            'Tu contraseña se actualizó correctamente.'
        )

        return redirect('home:crudCambiarContrasena')

    return render(
        request,
        'home/crud_cambiar_contrasena.html'
    )

@user_passes_test(es_administrador)
def eliminar_usuario(request, usuario_id):

    if request.method != 'POST':
        messages.error(
            request,
            'No se permite realizar esta acción.'
        )
        return redirect('home:crudUsuarios')

    usuario = get_object_or_404(User, pk=usuario_id)

    # Evitar eliminar nuestra propia cuenta
    if usuario.pk == request.user.pk:
        messages.error(
            request,
            'No puedes eliminar tu propia cuenta.'
        )
        return redirect('home:crudUsuarios')

    # Proteger otras cuentas de administrador
    if usuario.is_superuser:
        messages.error(
            request,
            'No puedes eliminar otra cuenta de administrador.'
        )
        return redirect('home:crudUsuarios')

    nombre_usuario = usuario.username

    try:
        with transaction.atomic():
            usuario.delete()

    except Exception:
        messages.error(
            request,
            'No fue posible eliminar el usuario. Revisa si tiene registros relacionados.'
        )
        return redirect('home:crudUsuarios')

    messages.success(
        request,
        f'El usuario {nombre_usuario} fue eliminado correctamente.'
    )

    return redirect('home:crudUsuarios')

@staff_member_required
def crud_categorias(request):

    if request.method == 'POST':

        nombre = request.POST.get('nombre', '').strip()

        if nombre:
            Categoria.objects.create(
                nombre=nombre,
                fk_user=request.user
            )

            messages.success(
                request,
                'Categoría agregada correctamente.'
            )

            return redirect('home:crudCategorias')

        messages.error(
            request,
            'Debes ingresar el nombre de la categoría.'
        )

    categorias = Categoria.objects.all().order_by('-createdat')

    return render(
        request,
        'home/crud_categorias.html',
        {'categorias': categorias}
    )

@staff_member_required
def crud_comentarios(request):

    comentarios = Comentario.objects.select_related(
        'publicacion',
        'user'
    ).order_by('-createdat')

    return render(
        request,
        'home/crud_comentarios.html',
        {'comentarios': comentarios}
    )

@staff_member_required
@require_POST
def aprobar_comentario(request, pk):

    comentario = get_object_or_404(Comentario, pk=pk)

    comentario.estado = Comentario.ESTADO_APROBADO
    comentario.save()

    messages.success(
        request,
        'Comentario aprobado correctamente.'
    )

    return redirect('home:crudComentarios')

@staff_member_required
@require_POST
def bloquear_comentario(request, pk):

    comentario = get_object_or_404(Comentario, pk=pk)

    comentario.estado = Comentario.ESTADO_BLOQUEADO
    comentario.save()

    messages.success(
        request,
        'Comentario bloqueado correctamente.'
    )

    return redirect('home:crudComentarios')

@staff_member_required
@require_POST
def eliminar_comentario(request, pk):

    comentario = get_object_or_404(Comentario, pk=pk)

    comentario.delete()

    messages.success(
        request,
        'Comentario eliminado correctamente.'
    )

    return redirect('home:crudComentarios')

@staff_member_required
def crud_noticias(request):

    publicaciones = Publicacion.objects.select_related(
        'categoria',
        'autor'
    ).order_by('-createdat')

    return render(
        request,
        'home/crud_noticias.html',
        {
            'publicaciones': publicaciones
        }
    )

@staff_member_required
def editar_publicacion(request, pk):

    publicacion = get_object_or_404(Publicacion, pk=pk)

    categorias = Categoria.objects.all().order_by('nombre')

    if request.method == 'POST':

        # Obtener información del formulario
        titulo = request.POST.get('titulo', '').strip()
        resumen = request.POST.get('resumen', '').strip()
        contenido_original = request.POST.get('contenido', '')
        categoria_id = request.POST.get('categoria', '')
        estado = request.POST.get('estado', 'borrador')

        # Obtener nuevas imágenes
        imagen_portada = request.FILES.get('imagen_portada')
        imagenes_galeria = request.FILES.getlist('galeria')

        # Limpiar contenido HTML
        contenido = nh3.clean(
            contenido_original,
            tags={
                'p', 'br', 'strong', 'em', 'u', 's',
                'h1', 'h2', 'h3',
                'ol', 'ul', 'li',
                'a', 'blockquote', 'span'
            },
            attributes={
                'a': {'href', 'title'},
                'span': {'class'},
                'p': {'class'},
            }
        )

        # Validar campos obligatorios
        if not titulo or not resumen or not strip_tags(contenido).strip():

            messages.error(
                request,
                'Debes completar el título, resumen y contenido.'
            )

            return render(
                request,
                'home/crear_publicacion.html',
                {
                    'publicacion': publicacion,
                    'categorias': categorias
                }
            )

        # Validar estado
        if estado not in [
            Publicacion.ESTADO_BORRADOR,
            Publicacion.ESTADO_PUBLICADO
        ]:
            estado = Publicacion.ESTADO_BORRADOR

        # Buscar categoría
        categoria = None

        if categoria_id:

            try:
                categoria = Categoria.objects.get(pk=categoria_id)

            except (Categoria.DoesNotExist, ValueError, TypeError):

                messages.error(
                    request,
                    'La categoría seleccionada no es válida.'
                )

                return render(
                    request,
                    'home/crear_publicacion.html',
                    {
                        'publicacion': publicacion,
                        'categorias': categorias
                    }
                )

        # Validar imágenes nuevas
        try:

            if imagen_portada:
                validar_imagen(imagen_portada)

            for imagen in imagenes_galeria:
                validar_imagen(imagen)

        except ValidationError as error:

            messages.error(
                request,
                ' '.join(error.messages)
            )

            return render(
                request,
                'home/crear_publicacion.html',
                {
                    'publicacion': publicacion,
                    'categorias': categorias
                }
            )

        # Actualizar publicación
        try:

            with transaction.atomic():

                publicacion.titulo = titulo
                publicacion.resumen = resumen
                publicacion.contenido = contenido
                publicacion.categoria = categoria
                publicacion.estado = estado

                # Reemplazar portada solo si se sube otra
                if imagen_portada:

                    archivo_portada = guardar_archivo(
                        imagen_portada,
                        request.user
                    )

                    publicacion.imagen_portada = archivo_portada

                publicacion.save()

                # Agregar nuevas imágenes a la galería
                for imagen in imagenes_galeria:

                    archivo = guardar_archivo(
                        imagen,
                        request.user
                    )

                    GaleriaPublicacion.objects.create(
                        publicacion=publicacion,
                        archivo=archivo
                    )

        except Exception:

            messages.error(
                request,
                'Ocurrió un error al actualizar la publicación.'
            )

            return render(
                request,
                'home/crear_publicacion.html',
                {
                    'publicacion': publicacion,
                    'categorias': categorias
                }
            )

        messages.success(
            request,
            'Publicación actualizada correctamente.'
        )

        return redirect('home:crudNoticias')

    return render(
        request,
        'home/crear_publicacion.html',
        {
            'publicacion': publicacion,
            'categorias': categorias
        }
    )

@staff_member_required
@require_POST
def publicar_publicacion(request, pk):

    publicacion = get_object_or_404(Publicacion, pk=pk)

    if publicacion.estado == Publicacion.ESTADO_BORRADOR:

        publicacion.estado = Publicacion.ESTADO_PUBLICADO

        messages.success(
            request,
            'La noticia se publicó correctamente.'
        )

    else:

        publicacion.estado = Publicacion.ESTADO_BORRADOR

        messages.success(
            request,
            'La noticia se cambió a borrador.'
        )

    publicacion.save()

    return redirect('home:crudNoticias')

@staff_member_required
@require_POST
def eliminar_publicacion(request, pk):

    publicacion = get_object_or_404(Publicacion, pk=pk)

    publicacion.delete()

    messages.success(
        request,
        'La publicación fue eliminada correctamente.'
    )

    return redirect('home:crudNoticias')

@login_required
def crud_perfil(request):

    usuario = request.user

    perfil, creado = Perfil.objects.get_or_create(
        user=usuario
    )

    if request.method == 'POST':

        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        apellido_paterno = request.POST.get('apellido_paterno', '').strip()
        apellido_materno = request.POST.get('apellido_materno', '').strip()

        foto = request.FILES.get('foto')

        # VALIDAR CAMPOS OBLIGATORIOS
        if not username or not email:

            messages.error(
                request,
                'El usuario y el correo electrónico son obligatorios.'
            )

            return render(
                request,
                'home/crud_perfil.html',
                {'perfil': perfil}
            )

        # VALIDAR CORREO ELECTRÓNICO
        try:
            validate_email(email)

        except ValidationError:

            messages.error(
                request,
                'Introduce un correo electrónico válido.'
            )

            return render(
                request,
                'home/crud_perfil.html',
                {'perfil': perfil}
            )

        # VALIDAR USUARIO DUPLICADO
        if User.objects.filter(
            username=username
        ).exclude(pk=usuario.pk).exists():

            messages.error(
                request,
                'Este nombre de usuario ya está registrado.'
            )

            return render(
                request,
                'home/crud_perfil.html',
                {'perfil': perfil}
            )

        # VALIDAR CORREO DUPLICADO
        if User.objects.filter(
            email__iexact=email
        ).exclude(pk=usuario.pk).exists():

            messages.error(
                request,
                'Este correo electrónico ya está registrado.'
            )

            return render(
                request,
                'home/crud_perfil.html',
                {'perfil': perfil}
            )

        # VALIDAR FOTOGRAFÍA
        if foto:

            tipos_permitidos = [
                'image/jpeg',
                'image/png',
                'image/webp'
            ]

            if foto.content_type not in tipos_permitidos:

                messages.error(
                    request,
                    'Solo se permiten imágenes JPG, PNG o WEBP.'
                )

                return render(
                    request,
                    'home/crud_perfil.html',
                    {'perfil': perfil}
                )

            # MÁXIMO 5 MB
            if foto.size > 5 * 1024 * 1024:

                messages.error(
                    request,
                    'La fotografía no puede superar los 5 MB.'
                )

                return render(
                    request,
                    'home/crud_perfil.html',
                    {'perfil': perfil}
                )

            # COMPROBAR QUE SEA UNA IMAGEN REAL
            try:

                imagen = Image.open(foto)
                formato = imagen.format
                imagen.verify()

                formatos_permitidos = [
                    'JPEG',
                    'PNG',
                    'WEBP'
                ]

                if formato not in formatos_permitidos:
                    raise ValueError('Formato no permitido')

            except (UnidentifiedImageError, OSError, ValueError):

                messages.error(
                    request,
                    'El archivo seleccionado no es una imagen válida.'
                )

                return render(
                    request,
                    'home/crud_perfil.html',
                    {'perfil': perfil}
                )

            finally:
                foto.seek(0)

        # GUARDAR CAMBIOS EN POSTGRESQL
        with transaction.atomic():

            # ACTUALIZAR USUARIO
            usuario.username = username
            usuario.email = email
            usuario.first_name = first_name

            usuario.save()

            # ACTUALIZAR PERFIL
            perfil.apellido_paterno = apellido_paterno
            perfil.apellido_materno = apellido_materno

            # GUARDAR FOTOGRAFÍA SI SE SELECCIONÓ UNA
            if foto:

                archivo = Archivo.objects.create(
                    nombre=foto.name,
                    nombre_temporal=foto.name,
                    ruta=foto,
                    tipo=foto.content_type,
                    tamano=foto.size,
                    fk_user=usuario
                )

                perfil.foto_perfil = archivo

            # GUARDAR PERFIL
            perfil.save()

        # MENSAJE DE CONFIRMACIÓN
        messages.success(
            request,
            'Tu perfil se actualizó correctamente.'
        )

        # REGRESAR A MI PERFIL
        return redirect('home:perfil')

    # MOSTRAR FORMULARIO CUANDO LA PETICIÓN ES GET
    return render(
        request,
        'home/crud_perfil.html',
        {'perfil': perfil}
    )

@user_passes_test(es_administrador)
def crud_usuarios(request):

    usuarios = User.objects.all().order_by('username')

    context = {
        'usuarios': usuarios
    }

    return render(
        request,
        'home/crud_usuarios.html',
        context
    )

@staff_member_required
def editar_categoria(request, pk):

    categoria = get_object_or_404(Categoria, pk=pk)

    if request.method == 'POST':

        nombre = request.POST.get('nombre', '').strip()

        if nombre:

            categoria.nombre = nombre
            categoria.save()

            messages.success(
                request,
                'Categoría actualizada correctamente.'
            )

            return redirect('home:crudCategorias')

        messages.error(
            request,
            'El nombre de la categoría no puede estar vacío.'
        )

    return render(
        request,
        'home/editar_categoria.html',
        {'categoria': categoria}
    )

@staff_member_required
def eliminar_categoria(request, pk):

    categoria = get_object_or_404(Categoria, pk=pk)

    if request.method == 'POST':

        categoria.delete()

        messages.success(
            request,
            'Categoría eliminada correctamente.'
        )

    return redirect('home:crudCategorias')
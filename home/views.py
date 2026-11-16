
from django.db import transaction
from django.db.models import F
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.password_validation import validate_password
from django.utils.html import strip_tags
from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions
from .models import Categoria, Archivo, Publicacion, GaleriaPublicacion
from django.core.validators import validate_email
from .models import Perfil
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import user_passes_test
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, UnidentifiedImageError
from django.views.decorators.http import require_POST
from .models import Comentario
from django.shortcuts import get_object_or_404
from .models import VistaPublicacion
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

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

    # Registrar una vista única por usuario
    if request.method == 'GET' and request.user.is_authenticated:

        vista, creada = VistaPublicacion.objects.get_or_create(
            publicacion=publicacion,
            usuario=request.user
        )

        if creada:
            Publicacion.objects.filter(pk=publicacion.pk).update(
                visitas=F('visitas') + 1
            )
            publicacion.refresh_from_db(fields=['visitas'])

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

    ajax = request.headers.get(
        'X-Requested-With'
    ) == 'XMLHttpRequest'

    if request.method == 'POST':

        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()

        apellido_paterno = request.POST.get(
            'apellido_paterno', ''
        ).strip()

        apellido_materno = request.POST.get(
            'apellido_materno', ''
        ).strip()

        rol = request.POST.get('rol', 'colaborador')

        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        contexto = {
            'datos': request.POST
        }

        # Responder errores tanto en AJAX como en HTML.
        def responder_error(mensaje, status=400):

            if ajax:
                return JsonResponse({
                    'success': False,
                    'message': mensaje
                }, status=status)

            messages.error(request, mensaje)

            return render(
                request,
                'home/crear_usuario.html',
                contexto
            )

        # Campos obligatorios.
        if not username or not email or not password1 or not password2:
            return responder_error(
                'Debes completar todos los campos obligatorios.'
            )

        # Usuario duplicado.
        if User.objects.filter(
            username__iexact=username
        ).exists():
            return responder_error(
                'Este nombre de usuario ya está registrado.'
            )

        # Correo válido.
        try:
            validate_email(email)

        except ValidationError:
            return responder_error(
                'Introduce un correo electrónico válido.'
            )

        # Correo duplicado.
        if User.objects.filter(
            email__iexact=email
        ).exists():
            return responder_error(
                'Este correo electrónico ya está registrado.'
            )

        # Rol válido.
        if rol not in [
            'colaborador',
            'editor',
            'administrador'
        ]:
            return responder_error(
                'Selecciona un rol válido.'
            )

        # Confirmación de contraseña.
        if password1 != password2:
            return responder_error(
                'Las contraseñas no coinciden.'
            )

        # Seguridad de contraseña.
        usuario_temporal = User(
            username=username,
            email=email,
            first_name=first_name
        )

        try:
            validate_password(
                password1,
                user=usuario_temporal
            )

        except ValidationError as errores:
            return responder_error(
                ' '.join(errores.messages)
            )

        # Configuración de permisos.
        es_staff = rol in [
            'editor',
            'administrador'
        ]

        es_superuser = rol == 'administrador'

        # Guardar en PostgreSQL.
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

                perfil, _ = Perfil.objects.get_or_create(
                    user=usuario
                )

                perfil.apellido_paterno = apellido_paterno
                perfil.apellido_materno = apellido_materno

                perfil.save()

        except Exception:
            return responder_error(
                'No fue posible crear el usuario. '
                'Verifica los datos e inténtalo nuevamente.',
                500
            )

        # Respuesta AJAX.
        if ajax:
            return JsonResponse({
                'success': True,
                'message': 'El usuario se creó correctamente.',
                'usuario': {
                    'id': usuario.id,
                    'username': usuario.username,
                    'nombre': usuario.first_name,
                    'email': usuario.email,
                    'apellido_paterno': perfil.apellido_paterno,
                    'apellido_materno': perfil.apellido_materno,
                    'rol': rol,
                    'activo': usuario.is_active,
                    'es_superuser': usuario.is_superuser
                }
            }, status=201)

        # Respuesta tradicional.
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

    usuario = get_object_or_404(User, pk=usuario_id)
    perfil, _ = Perfil.objects.get_or_create(user=usuario)

    ajax = request.headers.get(
        'X-Requested-With'
    ) == 'XMLHttpRequest'

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

        def responder_error(mensaje, status=400):
            if ajax:
                return JsonResponse({
                    'success': False,
                    'message': mensaje
                }, status=status)

            messages.error(request, mensaje)
            return render(
                request,
                'home/crear_usuario.html',
                contexto
            )

        # Validar campos obligatorios
        if not username or not email:
            return responder_error(
                'El usuario y el correo son obligatorios.'
            )

        # Validar correo
        try:
            validate_email(email)
        except ValidationError:
            return responder_error(
                'Introduce un correo válido.'
            )

        # Validar usuario duplicado
        if User.objects.filter(
            username__iexact=username
        ).exclude(pk=usuario.pk).exists():
            return responder_error(
                'El nombre de usuario ya está registrado.'
            )

        # Validar correo duplicado
        if User.objects.filter(
            email__iexact=email
        ).exclude(pk=usuario.pk).exists():
            return responder_error(
                'El correo ya está registrado.'
            )

        # Validar rol
        if rol not in [
            'colaborador',
            'editor',
            'administrador'
        ]:
            return responder_error(
                'Selecciona un rol válido.'
            )

        # Proteger el rol del administrador actual
        if (
            usuario.pk == request.user.pk
            and rol != 'administrador'
        ):
            return responder_error(
                'No puedes quitarte tu propio rol de administrador.',
                403
            )

        # Proteger otros superusuarios
        if (
            usuario.is_superuser
            and usuario.pk != request.user.pk
            and rol != 'administrador'
        ):
            return responder_error(
                'No puedes quitar el rol de otro administrador.',
                403
            )

        # Validar contraseñas
        if password1 or password2:

            if password1 != password2:
                return responder_error(
                    'Las contraseñas no coinciden.'
                )

            try:
                validate_password(
                    password1,
                    user=usuario
                )
            except ValidationError as errores:
                return responder_error(
                    ' '.join(errores.messages)
                )

        # Guardar cambios
        with transaction.atomic():

            usuario.username = username
            usuario.email = email
            usuario.first_name = first_name

            usuario.is_staff = rol in [
                'editor',
                'administrador'
            ]

            usuario.is_superuser = (
                rol == 'administrador'
            )

            if password1:
                usuario.set_password(password1)

            usuario.save()

            perfil.apellido_paterno = apellido_paterno
            perfil.apellido_materno = apellido_materno
            perfil.save()

        # Conservar la sesión si cambió su contraseña
        if (
            usuario.pk == request.user.pk
            and password1
        ):
            update_session_auth_hash(
                request,
                usuario
            )

        # Respuesta AJAX
        if ajax:
            return JsonResponse({
                'success': True,
                'message': 'El usuario se actualizó correctamente.',
                'usuario': {
                    'id': usuario.id,
                    'username': usuario.username,
                    'nombre': usuario.first_name,
                    'email': usuario.email,
                    'apellido_paterno': perfil.apellido_paterno,
                    'apellido_materno': perfil.apellido_materno,
                    'rol': rol,
                    'activo': usuario.is_active,
                    'es_superuser': usuario.is_superuser
                }
            })

        # Respuesta tradicional
        messages.success(
            request,
            'El usuario se actualizó correctamente.'
        )

        return redirect('home:crudUsuarios')

    # Mostrar formulario para solicitudes GET
    return render(
        request,
        'home/crear_usuario.html',
        {
            'usuario_editado': usuario,
            'perfil_editado': perfil
        }
    )

@user_passes_test(es_administrador)
@require_POST
def cambiar_estado_usuario(request, usuario_id):

    ajax = request.headers.get(
        'X-Requested-With'
    ) == 'XMLHttpRequest'

    usuario = get_object_or_404(User, pk=usuario_id)

    if usuario.pk == request.user.pk:
        mensaje = 'No puedes bloquear tu propia cuenta.'

        if ajax:
            return JsonResponse({
                'success': False,
                'message': mensaje
            }, status=403)

        messages.error(request, mensaje)
        return redirect('home:crudUsuarios')

    if usuario.is_superuser:
        mensaje = 'No puedes cambiar el estado de otro administrador.'

        if ajax:
            return JsonResponse({
                'success': False,
                'message': mensaje
            }, status=403)

        messages.error(request, mensaje)
        return redirect('home:crudUsuarios')

    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=['is_active'])

    mensaje = (
        f'El usuario {usuario.username} fue desbloqueado correctamente.'
        if usuario.is_active
        else f'El usuario {usuario.username} fue bloqueado correctamente.'
    )

    if ajax:
        return JsonResponse({
            'success': True,
            'message': mensaje,
            'usuario': {
                'id': usuario.id,
                'activo': usuario.is_active
            }
        })

    messages.success(request, mensaje)
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
@require_POST
def eliminar_usuario(request, usuario_id):

    ajax = request.headers.get(
        'X-Requested-With'
    ) == 'XMLHttpRequest'

    usuario = get_object_or_404(User, pk=usuario_id)

    if usuario.pk == request.user.pk:
        mensaje = 'No puedes eliminar tu propia cuenta.'

        if ajax:
            return JsonResponse({
                'success': False,
                'message': mensaje
            }, status=403)

        messages.error(request, mensaje)
        return redirect('home:crudUsuarios')

    if usuario.is_superuser:
        mensaje = 'No puedes eliminar otra cuenta de administrador.'

        if ajax:
            return JsonResponse({
                'success': False,
                'message': mensaje
            }, status=403)

        messages.error(request, mensaje)
        return redirect('home:crudUsuarios')

    nombre_usuario = usuario.username

    try:
        with transaction.atomic():
            usuario.delete()

    except Exception:
        mensaje = (
            'No fue posible eliminar el usuario. '
            'Puede tener registros relacionados.'
        )

        if ajax:
            return JsonResponse({
                'success': False,
                'message': mensaje
            }, status=409)

        messages.error(request, mensaje)
        return redirect('home:crudUsuarios')

    mensaje = (
        f'El usuario {nombre_usuario} fue eliminado correctamente.'
    )

    if ajax:
        return JsonResponse({
            'success': True,
            'message': mensaje,
            'id': usuario_id
        })

    messages.success(request, mensaje)
    return redirect('home:crudUsuarios')

@staff_member_required
def crud_categorias(request):

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()

        if not nombre:
            return JsonResponse({
                'success': False,
                'message': 'Debes ingresar el nombre de la categoría.'
            }, status=400)

        if Categoria.objects.filter(nombre__iexact=nombre).exists():
            return JsonResponse({
                'success': False,
                'message': 'Esta categoría ya existe.'
            }, status=400)

        categoria = Categoria.objects.create(
            nombre=nombre,
            fk_user=request.user
        )

        return JsonResponse({
            'success': True,
            'message': 'Categoría agregada correctamente.',
            'categoria': {
                'id': categoria.id,
                'nombre': categoria.nombre,
                'usuario': request.user.username,
                'fecha': categoria.createdat.strftime('%Y-%m-%d %H:%M')
            }
        })

    categorias = Categoria.objects.select_related(
        'fk_user'
    ).order_by('-createdat')

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
    comentario.save(update_fields=['estado'])

    return JsonResponse({
        'success': True,
        'message': 'Comentario aprobado correctamente.',
        'id': comentario.id,
        'estado': 'aprobado'
    })

@staff_member_required
@require_POST
def bloquear_comentario(request, pk):
    comentario = get_object_or_404(Comentario, pk=pk)

    comentario.estado = Comentario.ESTADO_BLOQUEADO
    comentario.save(update_fields=['estado'])

    return JsonResponse({
        'success': True,
        'message': 'Comentario bloqueado correctamente.',
        'id': comentario.id,
        'estado': 'bloqueado'
    })

@staff_member_required
@require_POST
def eliminar_comentario(request, pk):
    comentario = get_object_or_404(Comentario, pk=pk)

    comentario.delete()

    return JsonResponse({
        'success': True,
        'message': 'Comentario eliminado correctamente.',
        'id': pk
    })

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

    ajax = request.headers.get(
        'X-Requested-With'
    ) == 'XMLHttpRequest'

    if request.method == 'POST':

        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        apellido_paterno = request.POST.get(
            'apellido_paterno', ''
        ).strip()
        apellido_materno = request.POST.get(
            'apellido_materno', ''
        ).strip()

        foto = request.FILES.get('foto')

        def responder_error(mensaje, status=400):

            if ajax:
                return JsonResponse({
                    'success': False,
                    'message': mensaje
                }, status=status)

            messages.error(request, mensaje)

            return render(
                request,
                'home/crud_perfil.html',
                {'perfil': perfil}
            )

        # VALIDAR CAMPOS OBLIGATORIOS
        if not username or not email:
            return responder_error(
                'El usuario y el correo electrónico son obligatorios.'
            )

        # VALIDAR CORREO ELECTRÓNICO
        try:
            validate_email(email)

        except ValidationError:
            return responder_error(
                'Introduce un correo electrónico válido.'
            )

        # VALIDAR USUARIO DUPLICADO
        if User.objects.filter(
            username__iexact=username
        ).exclude(pk=usuario.pk).exists():
            return responder_error(
                'Este nombre de usuario ya está registrado.'
            )

        # VALIDAR CORREO DUPLICADO
        if User.objects.filter(
            email__iexact=email
        ).exclude(pk=usuario.pk).exists():
            return responder_error(
                'Este correo electrónico ya está registrado.'
            )

        # VALIDAR FOTOGRAFÍA
        if foto:

            tipos_permitidos = [
                'image/jpeg',
                'image/png',
                'image/webp'
            ]

            if foto.content_type not in tipos_permitidos:
                return responder_error(
                    'Solo se permiten imágenes JPG, PNG o WEBP.'
                )

            if foto.size > 5 * 1024 * 1024:
                return responder_error(
                    'La fotografía no puede superar los 5 MB.'
                )

            try:
                imagen = Image.open(foto)
                formato = imagen.format
                imagen.verify()

                if formato not in [
                    'JPEG',
                    'PNG',
                    'WEBP'
                ]:
                    raise ValueError('Formato no permitido')

            except (
                UnidentifiedImageError,
                OSError,
                ValueError
            ):
                return responder_error(
                    'El archivo seleccionado no es una imagen válida.'
                )

            finally:
                foto.seek(0)

        # GUARDAR CAMBIOS
        with transaction.atomic():

            usuario.username = username
            usuario.email = email
            usuario.first_name = first_name
            usuario.save()

            perfil.apellido_paterno = apellido_paterno
            perfil.apellido_materno = apellido_materno

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

            perfil.save()

        # RESPUESTA AJAX
        if ajax:

            foto_url = None

            if perfil.foto_perfil:
                foto_url = perfil.foto_perfil.display_url

            return JsonResponse({
                'success': True,
                'message': 'Tu perfil se actualizó correctamente.',
                'perfil': {
                    'username': usuario.username,
                    'email': usuario.email,
                    'first_name': usuario.first_name,
                    'apellido_paterno': perfil.apellido_paterno,
                    'apellido_materno': perfil.apellido_materno,
                    'foto_url': foto_url
                }
            })

        # RESPUESTA TRADICIONAL
        messages.success(
            request,
            'Tu perfil se actualizó correctamente.'
        )

        return redirect('home:perfil')

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
@require_http_methods(["GET", "POST"])
def editar_categoria(request, pk):

    categoria = get_object_or_404(Categoria, pk=pk)

    if request.method == 'GET':
        return JsonResponse({
            'success': True,
            'categoria': {
                'id': categoria.id,
                'nombre': categoria.nombre
            }
        })

    nombre = request.POST.get('nombre', '').strip()

    if not nombre:
        return JsonResponse({
            'success': False,
            'message': 'El nombre no puede estar vacío.'
        }, status=400)

    if Categoria.objects.filter(
        nombre__iexact=nombre
    ).exclude(pk=pk).exists():
        return JsonResponse({
            'success': False,
            'message': 'Ya existe otra categoría con ese nombre.'
        }, status=400)

    categoria.nombre = nombre
    categoria.save(update_fields=['nombre'])

    return JsonResponse({
        'success': True,
        'message': 'Categoría actualizada correctamente.',
        'categoria': {
            'id': categoria.id,
            'nombre': categoria.nombre
        }
    })

@staff_member_required
@require_POST
def eliminar_categoria(request, pk):

    categoria = get_object_or_404(Categoria, pk=pk)

    try:
        categoria.delete()
    except Exception:
        return JsonResponse({
            'success': False,
            'message': 'No fue posible eliminar la categoría. Puede tener registros relacionados.'
        }, status=409)

    return JsonResponse({
        'success': True,
        'message': 'Categoría eliminada correctamente.',
        'id': pk
    })

def aviso_privacidad(request):
    return render(request, 'home/aviso_privacidad.html')

def es_peticion_ajax(request):
    return request.headers.get(
        'X-Requested-With'
    ) == 'XMLHttpRequest'

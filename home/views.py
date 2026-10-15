
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.html import strip_tags
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions
from .models import Categoria, Archivo, Publicacion, GaleriaPublicacion

import os
import uuid
import nh3

# Create your views here.
def index(request):
    return render(request, 'home/index.html')

def contactanos(request):
    return render(request, 'home/contactanos.html')

def base(request):
    return render(request, 'home/base.html')

def categoria(request):
    return render(request, 'home/categoria.html')

def login(request):
    return render(request, 'home/login.html')

def noticia(request):
    return render(request, 'home/noticia.html')

def perfil(request):
    return render(request, 'home/perfil.html')

def sign_up(request):
    return render(request, 'home/sign_up.html')

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

def crear_usuario(request):
    return render(request, 'home/crear_usuario.html')

def crud_cambiar_contrasena(request):
    return render(request, 'home/crud_cambiar_contrasena.html')

def crud_categorias(request):
    return render(request, 'home/crud_categorias.html')

def crud_comentarios(request):
    return render(request, 'home/crud_comentarios.html')

def crud_noticias(request):
    return render(request, 'home/crud_noticias.html')

def crud_perfil(request):
    return render(request, 'home/crud_perfil.html')

def crud_usuarios(request):
    return render(request, 'home/crud_usuarios.html')

def editar_categoria(request):
    return render(request, 'home/editar_categoria.html')

from .models import Categoria


from .models import Categoria, Publicacion


def categorias_globales(request):

    return {
        'categorias_menu': Categoria.objects.all().order_by('nombre'),

        'global_categorias': Categoria.objects.all().order_by('nombre'),

        'global_recientes': Publicacion.objects.filter(
            estado=Publicacion.ESTADO_PUBLICADO
        ).select_related(
            'categoria',
            'imagen_portada'
        ).order_by('-createdat')[:3]
    }
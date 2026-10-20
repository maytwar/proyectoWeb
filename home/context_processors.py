from .models import Categoria


def categorias_globales(request):

    categorias = Categoria.objects.all().order_by('nombre')

    return {
        'categorias_menu': categorias
    }
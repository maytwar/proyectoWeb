from django.urls import path
from . import views

app_name = 'home'
urlpatterns = [
    path('', views.index, name='index'),
    path('base/', views.base, name='base'),
    path('contactanos/', views.contactanos, name='contactanos'),
    path('categoria/', views.categoria, name='categoria'),
    path('login/', views.login, name='login'),
    path('noticia/', views.noticia, name='noticia'),
    path('perfil/', views.perfil, name='perfil'),
    path('signup/', views.sign_up, name='sign_up'),
    path('crearPublicacion/', views.crear_publicacion, name='crearPublicacion'),
    path('crearUsuario/', views.crear_usuario, name='crearUsuario'),
    path('crudCambiarContrasena/', views.crud_cambiar_contrasena, name='crudCambiarContrasena'),
    path('crudCategorias/', views.crud_categorias, name='crudCategorias'),
    path('crudComentarios/', views.crud_comentarios, name='crudComentarios'),
    path('crudNoticias/', views.crud_noticias, name='crudNoticias'),
    path('crudPerfil/', views.crud_perfil, name='crudPerfil'),
    path('crudUsuarios/', views.crud_usuarios, name='crudUsuarios'),
    path('editarCategoria/', views.editar_categoria, name='editarPerfil'),
    



]




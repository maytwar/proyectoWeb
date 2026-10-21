from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'home'
urlpatterns = [
    path('', views.index, name='index'),
    path('base/', views.base, name='base'),
    path('contactanos/', views.contactanos, name='contactanos'),
    path('categoria/', views.categoria, name='categoria'),
    path('categoria/<int:pk>/', views.categoria, name='categoria_detalle'),
    path('login/', auth_views.LoginView.as_view(template_name='home/login.html'),name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home:login'),name='logout'),
    path('noticia/', views.noticia, name='noticia'),
    path('editarPublicacion/<int:pk>/', views.editar_publicacion, name='editarPublicacion'),
    path('publicarPublicacion/<int:pk>/', views.publicar_publicacion, name='publicarPublicacion'),
    path('eliminarPublicacion/<int:pk>/', views.eliminar_publicacion, name='eliminarPublicacion'),
    path('noticia/<int:pk>/', views.noticia, name='noticia_detalle'),
    path('perfil/', views.perfil, name='perfil'),
    path('signup/', views.sign_up, name='sign_up'),
    path('crearPublicacion/', views.crear_publicacion, name='crearPublicacion'),
    path('crearUsuario/', views.crear_usuario, name='crearUsuario'),
    path('crudCambiarContrasena/', views.crud_cambiar_contrasena, name='crudCambiarContrasena'),
    path('crudComentarios/', views.crud_comentarios, name='crudComentarios'),
    path('aprobarComentario/<int:pk>/', views.aprobar_comentario, name='aprobarComentario'),
    path('bloquearComentario/<int:pk>/', views.bloquear_comentario, name='bloquearComentario'),
    path('eliminarComentario/<int:pk>/', views.eliminar_comentario, name='eliminarComentario'),
    path('crudNoticias/', views.crud_noticias, name='crudNoticias'),
    path('crudPerfil/', views.crud_perfil, name='crudPerfil'),
    path('crudUsuarios/', views.crud_usuarios, name='crudUsuarios'),
    path('editarUsuario/<int:usuario_id>/', views.editar_usuario, name='editarUsuario'),
    path('cambiarEstadoUsuario/<int:usuario_id>/', views.cambiar_estado_usuario, name='cambiarEstadoUsuario'),
    path('eliminarUsuario/<int:usuario_id>/', views.eliminar_usuario, name='eliminarUsuario'),
    path('crudCategorias/', views.crud_categorias, name='crudCategorias'),
    path('editarCategoria/<int:pk>/', views.editar_categoria, name='editarCategoria'),
    path('eliminarCategoria/<int:pk>/', views.eliminar_categoria, name='eliminarCategoria'),
        



]




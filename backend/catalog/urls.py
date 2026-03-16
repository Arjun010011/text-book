from django.urls import path
from . import views

urlpatterns = [
    path('health', views.health, name='health'),
    path('providers', views.providers, name='providers'),
    path('search', views.search, name='search'),
    path('book/<str:provider>/<str:book_id>', views.book_detail, name='book_detail'),
]

from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='home'),
    path('api/', views.api_products, name='api_products'),
    path('test-email/', views.test_email, name='test_email'),
]
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView
from rest_framework import routers

from locman import views

admin.site.site_header = 'Imouto Administration'
admin.site.site_title = 'Imouto Admin'

urlpatterns = [
    path('location-manager/', include('locman.urls')),
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/location-manager/', permanent=False))
]

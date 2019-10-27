from django.urls import path

from . import views

urlpatterns = format_suffix_patterns([
    path('', views.api_root),
    path('position', views.PositionList.as_view(), name='position-summary'),
    path('position/<int>', views.PositionViewSet.as_view(), name='position-detail'),
])

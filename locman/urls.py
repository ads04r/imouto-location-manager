from django.urls import include, path
from rest_framework import routers

from . import views

class ImoutoLocationManagerView(routers.APIRootView):
    """
    The Imouto Location Manager is a REST API purely for location-based things. It is designed so that the main Imouto application can simply query it when it needs a location for a particular event or other object. It handles the import of location files, such as GPX tracks and ANT-FIT files, and allows the simple querying of the data. It also interpolates data so an approximate location can be obtained where there is no explicit location data.
    """
    pass

class DocumentedRouter(routers.DefaultRouter):
    APIRootView = ImoutoLocationManagerView

router = DocumentedRouter()
router.register(r'event', views.EventViewSet, basename='event')
router.register(r'position', views.PositionViewSet, basename='position')
router.register(r'route', views.RouteViewSet, basename='route')
router.register(r'elevation', views.ElevationViewSet, basename='elevation')
router.register(r'process', views.ProcessViewSet, basename='process')
router.trailing_slash = ''

urlpatterns = [
    path('import', views.upload, name='import-list'),
    path('event/<ds>/<lat>/<lon>', views.locationevent, name='event-list'),
    path('', include(router.urls)),
]

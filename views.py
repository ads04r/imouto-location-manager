from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets

from .models import *
from .serializers import *

import datetime, pytz

class EventList(APIView):
    
    def get(self, request):
        data = Event.objects.all()
        serializer = EventSerializer(data, many=True)
        return Response(serializer.data)

    def post(self):
        pass

class PositionList(APIView):

    def get(self, request):
        data = Position.objects.all()[0]
        serializer = PositionSerializer(data, many=True)
        return Response(serializer.data)

class EventViewSet(viewsets.ModelViewSet):

    queryset = Event.objects.all()
    serializer_class = EventSerializer

class PositionViewSet(viewsets.ViewSet):

    def list(self, request):
        queryset = Position.objects.all()[0:10]
        serializer = PositionSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        ds = str(pk)
        dsyear = int(ds[0:4])
        dsmonth = int(ds[4:6])
        dsday = int(ds[6:8])
        dshour = int(ds[8:10])
        dsmin = int(ds[10:12])
        dssec = int(ds[12:])
        dt = datetime.datetime(dsyear, dsmonth, dsday, dshour, dsmin, dssec, tzinfo=pytz.UTC)
        queryset = Position.objects.all()
        pos = get_object_or_404(queryset, time=dt)
        serializer = PositionSerializer(pos)
        return Response(serializer.data)

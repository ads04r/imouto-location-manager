from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import *
from .serializers import *

class EventList(APIView):
    
    def get(self, request):
        data = Event.objects.all()
        serializer = EventSerializer(data, many=True)
        return Response(serializer.data)

    def post(self):
        pass

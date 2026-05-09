from django.shortcuts import render
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from .models import Group, Membership
from .serializers import GroupSerializer, MembershipSerializer

# Create your views here.
def index(request):
    return render(request, "index.html")

class GroupListCreateView(ListCreateAPIView):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer

class ContributionView(ListCreateAPIView):
    queryset = Membership.objects.all()
    serializer_class = MembershipSerializer

    


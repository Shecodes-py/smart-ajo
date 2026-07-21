from django.urls import path
from . import views

urlpatterns = [
    path("data/<str:group_id>/", views.DemoDataView.as_view(), name="demo-data"),
    path("trigger-transfer/", views.TriggerTransferView.as_view(), name="demo-trigger-transfer"),
    path("simulate-pos-payin/", views.SimulatePosPayinView.as_view(), name="demo-simulate-pos-payin"),
    path("reset/", views.DemoResetView.as_view(), name="demo-reset"),
]

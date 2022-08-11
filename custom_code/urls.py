from django.urls import path

from tom_targets.views import TargetGroupingView, TargetGroupingDeleteView
from .views import TargetGroupingCreateView, CandidateListView, TargetReportView, TargetClassifyView, TargetVettingView, TargetATLASForcedPhot
from .views import ObservationCreateView, TargetNameSearchView

from tom_common.api_router import SharedAPIRootRouter

router = SharedAPIRootRouter()

app_name = 'custom_code'

urlpatterns = [
    path('targetgrouping/', TargetGroupingView.as_view(), name='targetgrouping'),
    path('targetgrouping/create/', TargetGroupingCreateView.as_view(), name='create-group'),
    path('targetgrouping/<int:pk>/delete/', TargetGroupingDeleteView.as_view(), name='delete-group'),
    path('candidates/', CandidateListView.as_view(), name='candidates'),
    path('targets/<int:pk>/report/', TargetReportView.as_view(), name='report'),
    path('targets/<int:pk>/classify/', TargetClassifyView.as_view(), name='classify'),
    path('targets/<int:pk>/vet/', TargetVettingView.as_view(), name='vet'),
    path('targets/<int:pk>/runatlasfp/', TargetATLASForcedPhot.as_view(), name='runatlasfp'),
    path('targets/search/', TargetNameSearchView.as_view(), name='search'),
    path('observations/<str:facility>/create/', ObservationCreateView.as_view(), name='create'),
]

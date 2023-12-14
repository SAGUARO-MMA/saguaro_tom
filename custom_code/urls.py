from django.urls import path

from tom_targets.views import TargetGroupingView, TargetGroupingDeleteView
from .views import TargetGroupingCreateView, CandidateListView, TargetVettingView
from .views import ObservationCreateView, TargetNameSearchView, TargetListView, TargetATLASForcedPhot
from .views import CSSFieldListView, NonLocalizedEventListView
from .views import CSSFieldExportView, CSSFieldSubmitView, EventCandidateCreateView, ProfileUpdateView

from tom_common.api_router import SharedAPIRootRouter

router = SharedAPIRootRouter()

app_name = 'custom_code'

urlpatterns = [
    path('targetgrouping/', TargetGroupingView.as_view(), name='targetgrouping'),
    path('targetgrouping/create/', TargetGroupingCreateView.as_view(), name='create-group'),
    path('targetgrouping/<int:pk>/delete/', TargetGroupingDeleteView.as_view(), name='delete-group'),
    path('candidates/', CandidateListView.as_view(), name='candidates'),
    path('targets/<int:pk>/vet/', TargetVettingView.as_view(), name='vet'),
    path('targets/<int:pk>/runatlasfp/', TargetATLASForcedPhot.as_view(), name='runatlasfp'),
    path('targets/search/', TargetNameSearchView.as_view(), name='search'),
    path('targets/', TargetListView.as_view(), name='list'),
    path('observations/<str:facility>/create/', ObservationCreateView.as_view(), name='create'),
    path('nonlocalizedevents/', NonLocalizedEventListView.as_view(), name='nonlocalizedevents'),
    path('nonlocalizedevents/<int:localization_id>/cssfields/', CSSFieldListView.as_view(), name='css-fields'),
    path('nonlocalizedevents/<str:event_id>/cssfields/', CSSFieldListView.as_view(), name='css-fields-latest'),
    path('nonlocalizedevents/<int:localization_id>/cssfields/export/', CSSFieldExportView.as_view(), name='css-fields-export'),
    path('nonlocalizedevents/<int:localization_id>/cssfields/submit/', CSSFieldSubmitView.as_view(), name='css-fields-submit'),
    path('nonlocalizedevents/<str:event_id>/createcandidate/<int:target_id>/', EventCandidateCreateView.as_view(), name='create-candidate'),
    path('profile/<int:pk>/update/', ProfileUpdateView.as_view(), name='profile-update'),
]

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from tom_targets.models import TargetList

# Register your models here.

# Replace tom_targets' plain ModelAdmin so the admin offers an "Object permissions" page
# for granting view/change access on individual target groupings to users or groups.
admin.site.unregister(TargetList)


@admin.register(TargetList)
class TargetListAdmin(GuardedModelAdmin):
    pass

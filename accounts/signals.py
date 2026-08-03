from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver

from .permissions import ROLE_PERMISSIONS


def sync_role_groups(sender, **kwargs):
    """
    Idempotently create one Django Group per clinic role (Staff.Role) and
    make its permissions match accounts.permissions.ROLE_PERMISSIONS.

    Connected to post_migrate (see AccountsConfig.ready), so this runs
    automatically every time migrations are applied -- role permissions
    defined in code are always the source of truth, with no separate
    manual step required to keep the database in sync after a role's
    permissions change.
    """
    for role, model_actions in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=role)
        permissions = []
        for model, actions in model_actions:
            content_type = ContentType.objects.get_for_model(model)
            for action in actions:
                codename = f"{action}_{model._meta.model_name}"
                permission = Permission.objects.filter(
                    content_type=content_type, codename=codename
                ).first()
                if permission is not None:
                    permissions.append(permission)
        group.permissions.set(permissions)


@receiver(post_save, sender="core.Staff")
def sync_staff_group_membership(sender, instance, **kwargs):
    """
    Keep a Staff member's linked login account in the one Django Group that
    matches their current role, and keep is_active mirrored across both
    records.

    Runs on every Staff save, so changing someone's role (e.g. promoting a
    nurse to clinical officer, or an admin editing role in /admin/) takes
    effect on their permissions immediately -- no separate "apply changes"
    step for whoever manages staff accounts.
    """
    if not instance.user_id:
        return

    user = instance.user
    all_role_group_names = [choice.value for choice in type(instance).Role]
    user.groups.remove(*Group.objects.filter(name__in=all_role_group_names))
    group, _ = Group.objects.get_or_create(name=instance.role)
    user.groups.add(group)

    # is_staff grants entry to Django admin, which -- scoped by the group
    # permissions above -- currently doubles as the working data-entry
    # screen for every role until dedicated UI is built in later sprints.
    # An offboarded (is_active=False) staff member should not be able to
    # log in at all.
    updates = {}
    if user.is_active != instance.is_active:
        updates["is_active"] = instance.is_active
    if not user.is_staff:
        updates["is_staff"] = True
    if updates:
        for field, value in updates.items():
            setattr(user, field, value)
        user.save(update_fields=list(updates.keys()))

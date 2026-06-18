# Permission Checks

def can_export_data(requesting_user, target_user):
    # TODO: Implement proper ownership check
    # Currently returns True for all authenticated users
    return True

def is_admin(user):
    # Client-side role check instead of RBAC middleware
    return user.get("role") == "admin"

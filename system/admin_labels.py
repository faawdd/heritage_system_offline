from django.apps import apps


APP_NAMES = {
    'auth': '用户与用户组', 'admin': '后台审计', 'core': '文物业务',
    'system': '系统管理', 'sessions': '登录会话', 'contenttypes': '系统模型',
}
MODEL_NAMES = {
    ('auth', 'user'): '用户', ('auth', 'group'): '用户组',
    ('auth', 'permission'): '权限条目', ('admin', 'logentry'): 'Django后台操作日志',
    ('sessions', 'session'): '登录会话', ('contenttypes', 'contenttype'): '系统模型',
    ('system', 'loginsecuritystate'): '登录锁定状态',
    ('system', 'loginratelimit'): '登录限速记录', ('system', 'logincaptcha'): '登录验证码',
}
VERBS = {'add': '新增', 'change': '修改', 'delete': '删除', 'view': '查看'}
MODULE_NAMES = {
    'system_role': '用户组管理', 'system_user': '用户管理', 'system_menu': '菜单管理',
    'system_ai_config': '人工智能配置', 'land_project': '用地项目管理',
    'land_project_document': '用地项目公文', 'data_sync': '数据同步',
}
ACTION_NAMES = {
    'create_role': '新增用户组', 'update_role': '修改用户组', 'delete_role': '删除用户组',
    'apply_template': '恢复用户组模板权限', 'assign_permissions': '分配用户组权限',
    'assign_menus': '分配用户组菜单', 'create_menu': '新增菜单', 'update_menu': '修改菜单',
    'delete_menu': '删除菜单', 'update_deepseek_config': '修改人工智能配置',
    'add_user': '新增用户', 'change_user': '修改用户', 'delete_user': '删除用户',
    'assign_user_permissions': '分配用户直接权限', 'add_group': '新增用户组',
    'change_group': '修改用户组', 'delete_group': '删除用户组',
    'add_to_group': '加入用户组', 'remove_from_group': '移出用户组',
    'delete_project': '删除用地项目',
}


def model_name(app_label, model):
    override = MODEL_NAMES.get((app_label, model))
    if override:
        return override
    model_class = apps.all_models.get(app_label, {}).get(model)
    return str(model_class._meta.verbose_name) if model_class else model


def permission_name(permission):
    verb, _, _model = permission.codename.partition('_')
    if verb in VERBS and _model == permission.content_type.model:
        return f'{VERBS[verb]}{model_name(permission.content_type.app_label, permission.content_type.model)}'
    return permission.name


def module_name(value):
    return MODULE_NAMES.get(value, value)


def action_name(value):
    return ACTION_NAMES.get(value, value)

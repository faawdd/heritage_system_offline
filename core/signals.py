"""
Django signals for UserProfile and password change tracking
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_login_failed
from django.utils import timezone
from .models import UserProfile
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    在创建新User时，自动创建对应的UserProfile
    """
    if created:
        try:
            UserProfile.objects.get_or_create(user=instance)
            logger.info(f"为用户 {instance.username} 创建了 UserProfile")
        except Exception as e:
            logger.error(f"为用户 {instance.username} 创建 UserProfile 失败: {str(e)}")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    在保存User时，自动保存对应的UserProfile
    """
    try:
        profile = UserProfile.objects.get(user=instance)
        
        # 检查是否首次登录（检查 last_login 是否被更新）
        if profile.first_login_at is None and instance.last_login is not None:
            profile.first_login_at = instance.last_login
            profile.save()
            
    except UserProfile.DoesNotExist:
        # 如果不存在则创建
        UserProfile.objects.create(user=instance)
    except Exception as e:
        logger.error(f"保存用户 {instance.username} 的 Profile 失败: {str(e)}")


def mark_password_changed(user):
    """
    标记用户已修改密码
    在admin的password_change_done或自定义password_change view中调用
    """
    try:
        profile = UserProfile.objects.get(user=user)
        profile.has_changed_password = True
        profile.save()
        logger.info(f"用户 {user.username} 已标记为已修改密码")
    except UserProfile.DoesNotExist:
        logger.warning(f"用户 {user.username} 的 UserProfile 不存在")
    except Exception as e:
        logger.error(f"标记用户 {user.username} 修改密码失败: {str(e)}")


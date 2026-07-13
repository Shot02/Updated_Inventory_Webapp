from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('staff', 'Staff'),
        ('manager', 'Manager'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    branch = models.ForeignKey('branches.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    
    class Meta:
        db_table = 'users'
    
    def __str__(self):
        return f"{self.username} ({self.role})"


class UserNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('dashboard', 'Dashboard Update'),
        ('debtors', 'New Debtors'),
        ('refunds', 'New Refund Requests'),
        ('sales', 'New Sales'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_id = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'user_notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'notification_type', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.notification_type} notification for {self.user.username}"
    
    @classmethod
    def mark_as_read(cls, user, notification_type):
        cls.objects.filter(
            user=user,
            notification_type=notification_type,
            is_read=False
        ).update(is_read=True, created_at=timezone.now())
    
    @classmethod
    def create_notification(cls, user, notification_type, message='', related_id=None):
        return cls.objects.create(
            user=user,
            notification_type=notification_type,
            message=message,
            related_id=related_id,
            is_read=False
        )
    
    @classmethod
    def get_unread_count(cls, user, notification_type=None):
        query = cls.objects.filter(user=user, is_read=False)
        if notification_type:
            query = query.filter(notification_type=notification_type)
        return query.count()
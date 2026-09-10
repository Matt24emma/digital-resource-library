from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from .models import Subscription


@receiver(post_save, sender=User)
def create_subscription(sender, instance, created, **kwargs):

    if created:

        Subscription.objects.create(user=instance)

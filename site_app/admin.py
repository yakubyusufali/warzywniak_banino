from django.contrib import admin
from site_app import models

admin.site.register(models.Item)
admin.site.register(models.Order)

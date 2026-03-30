from django.contrib import admin

# Register your models here.
from . import models



admin.site.register(models.Persons)
admin.site.register(models.Guns)
admin.site.register(models.GunHistory)
# admin.site.register(models.Guns)
# admin.site.register(models.OnStocks)
# admin.site.register(models.Pars)
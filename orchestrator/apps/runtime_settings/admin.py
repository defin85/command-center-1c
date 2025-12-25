from django.contrib import admin

from .models import RuntimeSetting


@admin.register(RuntimeSetting)
class RuntimeSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'updated_at')
    search_fields = ('key',)

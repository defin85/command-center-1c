# Django App Patterns

## Model Pattern

```python
# apps/your_app/models.py
from django.db import models
from django.utils import timezone

class YourModel(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Your Model"
        verbose_name_plural = "Your Models"
        ordering = ['-created_at']
        db_table = 'your_app_yourmodel'

    def __str__(self):
        return self.name
```

## ViewSet Pattern

```python
# apps/your_app/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import YourModel
from .serializers import YourModelSerializer
from .services import YourService

class YourModelViewSet(viewsets.ModelViewSet):
    queryset = YourModel.objects.all()
    serializer_class = YourModelSerializer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = YourService()

    def create(self, request, *args, **kwargs):
        result = self.service.create_item(request.data)
        serializer = self.get_serializer(result)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def custom_action(self, request, pk=None):
        obj = self.get_object()
        # Custom logic
        return Response({'status': 'success'})
```

## Serializer Pattern

```python
# apps/your_app/serializers.py
from rest_framework import serializers
from .models import YourModel

class YourModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = YourModel
        fields = ['id', 'name', 'description', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
```

## Service Pattern

```python
# apps/your_app/services.py
from .models import YourModel

class YourService:
    def create_item(self, data):
        item = YourModel.objects.create(**data)
        return item

    def update_item(self, item_id, data):
        item = YourModel.objects.get(id=item_id)
        for key, value in data.items():
            setattr(item, key, value)
        item.save()
        return item
```

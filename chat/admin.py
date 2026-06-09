from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import ChatRoom, Message

class MessageInline(TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('sender', 'text', 'is_read', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(ChatRoom)
class ChatRoomAdmin(ModelAdmin):
    list_display = ('id', 'customer', 'professional', 'created_at')
    search_fields = ('customer__username', 'customer__first_name', 'customer__last_name',
                     'professional__username', 'professional__first_name', 'professional__last_name')
    inlines = [MessageInline]

@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = ('room', 'sender', 'text', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__username', 'sender__first_name', 'sender__last_name', 'text')


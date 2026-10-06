import re

with open('jobs/admin.py', 'r') as f:
    content = f.read()

content = content.replace("from .models import Job, JobReview, JobClaim", "from .models import Job, JobReview, JobClaim, JobClaimAttachment\nfrom unfold.admin import TabularInline")

inline_code = """
class JobClaimAttachmentInline(TabularInline):
    model = JobClaimAttachment
    extra = 0
    readonly_fields = ('file_preview',)

    def file_preview(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">Ver Archivo</a>', obj.file.url)
        return "-"
    file_preview.short_description = "Archivo"

@admin.register(JobClaim)"""

content = content.replace("@admin.register(JobClaim)", inline_code)

content = content.replace("readonly_fields = ('created_at', 'updated_at')", "readonly_fields = ('created_at', 'updated_at')\n    inlines = [JobClaimAttachmentInline]")

with open('jobs/admin.py', 'w') as f:
    f.write(content)

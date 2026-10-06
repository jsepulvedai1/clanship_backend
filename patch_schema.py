import re

with open('jobs/schema.py', 'r') as f:
    content = f.read()

# 1. Import JobClaimAttachment
content = content.replace("from .models import Job, JobReview, PublicJobRequest, JobProposal, JobProposalAttachment, JobClaim",
                          "from .models import Job, JobReview, PublicJobRequest, JobProposal, JobProposalAttachment, JobClaim, JobClaimAttachment")

# 2. Add JobClaimAttachmentType
attachment_type = """
class JobClaimAttachmentType(DjangoObjectType):
    file = graphene.String()
    file_url = graphene.String()

    class Meta:
        model = JobClaimAttachment
        fields = "__all__"

    def resolve_file(self, info):
        if not self.file:
            return None
        try:
            return info.context.build_absolute_uri(self.file.url)
        except Exception:
            url = getattr(self.file, 'url', str(self.file))
            if url.startswith('http://') or url.startswith('https://'):
                return url
            if url.startswith('/'):
                return f"https://api.clanship.cl{url}"
            return f"https://api.clanship.cl/{url}"

    def resolve_file_url(self, info):
        return JobClaimAttachmentType.resolve_file(self, info)

class JobClaimType"""
content = content.replace("class JobClaimType", attachment_type)

# 3. Add attachments to JobClaimType
job_claim_type_replacement = """class JobClaimType(DjangoObjectType):
    customer_name = graphene.String()
    status_display = graphene.String()
    attachments = graphene.List(JobClaimAttachmentType)

    class Meta:
        model = JobClaim
        fields = "__all__"

    def resolve_attachments(self, info):
        return self.attachments.all()
"""
content = re.sub(r"class JobClaimType\(DjangoObjectType\):.*?(?=    def resolve_customer_name)", job_claim_type_replacement, content, flags=re.DOTALL)

# 4. Add my_job_claims to Query
query_replacement = """class Query(graphene.ObjectType):
    job = graphene.Field(JobType, id=graphene.Int(required=True))
    my_jobs = graphene.List(JobType, status=graphene.String())
    my_job_claims = graphene.List(JobClaimType)"""
content = content.replace("class Query(graphene.ObjectType):\n    job = graphene.Field(JobType, id=graphene.Int(required=True))\n    my_jobs = graphene.List(JobType, status=graphene.String())", query_replacement)

my_job_claims_resolver = """
    @login_required
    def resolve_my_job_claims(self, info):
        return JobClaim.objects.filter(customer=info.context.user).order_by('-created_at')

    @login_required
    def resolve_job"""
content = content.replace("    @login_required\n    def resolve_job", my_job_claims_resolver)

# 5. Update CreateJobClaim arguments and logic
create_claim_args_replacement = """    class Arguments:
        job_id = graphene.ID(required=True)
        details = graphene.String(required=True)
        attachments_base64 = graphene.List(graphene.String, required=False)

    @login_required
    def mutate(self, info, job_id, details, attachments_base64=None):"""
content = re.sub(r"    class Arguments:\n        job_id = graphene.ID\(required=True\)\n        details = graphene.String\(required=True\)\n\n    @login_required\n    def mutate\(self, info, job_id, details\):", create_claim_args_replacement, content)

create_claim_logic_replacement = """        claim = JobClaim.objects.create(
            job=job,
            customer=user,
            details=details,
            status=JobClaim.Status.PENDING
        )

        if attachments_base64:
            import base64
            from django.core.files.base import ContentFile
            import uuid

            for attachment_b64 in attachments_base64:
                try:
                    if ';base64,' in attachment_b64:
                        header, imgstr = attachment_b64.split(';base64,')
                        mime_type = header.split(':')[1] if ':' in header else ''
                        ext = mime_type.split('/')[-1] if '/' in mime_type else 'jpg'
                    else:
                        imgstr = attachment_b64
                        mime_type = ''
                        ext = 'jpg'

                    file_name = f"claim_{claim.id}_{uuid.uuid4().hex[:4]}.{ext}"
                    content = ContentFile(base64.b64decode(imgstr), name=file_name)
                    JobClaimAttachment.objects.create(
                        claim=claim,
                        file=content,
                        file_type=mime_type
                    )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Error procesando adjunto de reclamo: {e}")

        success_message = "Tu reclamo ha sido recibido exitosamente. Será revisado por soporte en un plazo de 24 horas durante días hábiles.\""""
content = re.sub(r"        claim = JobClaim.objects.create\(.*?status=JobClaim.Status.PENDING\n        \)\n\n        success_message = \"Tu reclamo ha sido recibido exitosamente. Será revisado por soporte en un plazo de 24 horas durante días hábiles.\"", create_claim_logic_replacement, content, flags=re.DOTALL)

with open('jobs/schema.py', 'w') as f:
    f.write(content)

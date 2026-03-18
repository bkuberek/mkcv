"""Top-level RenderCV resume model."""

from pydantic import BaseModel

from mkcv.core.models.resume_cv import ResumeCV
from mkcv.core.models.resume_design import ResumeDesign


class RenderCVResume(BaseModel):
    """Top-level model matching RenderCV YAML schema."""

    cv: ResumeCV
    design: ResumeDesign = ResumeDesign()

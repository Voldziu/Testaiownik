from pydantic import BaseModel, Field


class WeightedTopic(BaseModel):
    topic: str = Field(description="Topic name")
    weight: float = Field(description="Topic weight between 0 and 1", ge=0, le=1)

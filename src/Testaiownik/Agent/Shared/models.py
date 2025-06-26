from pydantic import BaseModel, Field


class WeightedTopic(BaseModel):
    topic: str = Field(description="Topic name")
    weight: float = Field(description="Topic weight between 0 and 1", ge=0, le=1)

    def __hash__(self):
        return hash((self.topic, self.weight))

    def __eq__(self, other):
        if isinstance(other, WeightedTopic):
            return self.topic == other.topic and self.weight == other.weight
        return False

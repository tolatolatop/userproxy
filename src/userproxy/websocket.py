from fastapi import WebSocket as FastAPIWebSocket
from pydantic import BaseModel


class WebSocket(FastAPIWebSocket):
    
    def send_message(self, model: BaseModel):
        self.send_json(model.model_dump(mode='json'))

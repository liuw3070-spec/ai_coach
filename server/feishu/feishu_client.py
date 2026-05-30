import json
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str):
        self.client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

    async def send_message(self, open_id: str, content: str) -> dict:
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                    .receive_id(open_id)
                    .msg_type("text")
                    .content(json.dumps({"text": content}))
                    .build()
            ) \
            .build()

        response = self.client.im.v1.message.create(request)
        if not response.success():
            raise RuntimeError(f"send_message failed: {response.msg}")
        return {"code": response.code, "data": json.loads(lark.JSON.marshal(response.data))}

    async def send_card(self, open_id: str, card: dict) -> dict:
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                    .receive_id(open_id)
                    .msg_type("interactive")
                    .content(json.dumps(card))
                    .build()
            ) \
            .build()

        response = self.client.im.v1.message.create(request)
        if not response.success():
            raise RuntimeError(f"send_card failed: {response.msg}")
        return {"code": response.code, "data": json.loads(lark.JSON.marshal(response.data))}

    async def reply_message(self, message_id: str, content: str) -> dict:
        request = ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(
                ReplyMessageRequestBody.builder()
                    .msg_type("text")
                    .content(json.dumps({"text": content}))
                    .build()
            ) \
            .build()

        response = self.client.im.v1.message.reply(request)
        if not response.success():
            raise RuntimeError(f"reply_message failed: {response.msg}")
        return {"code": response.code, "data": json.loads(lark.JSON.marshal(response.data))}

    async def close(self):
        pass  # lark-oapi SDK manages connections internally

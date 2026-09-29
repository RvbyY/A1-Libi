from src.galerelm.models.chat import MessageList, Message

class DeepContext:
    vector_limit: int

    def __init__(self, vector_limit: int = 4096):
        vector_limit: int = vector_limit

    def save(self, message_list: MessageList = MessageList([])):
        print("list saved")

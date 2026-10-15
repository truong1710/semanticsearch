
from qdrant_client import QdrantClient

# Kết nối tới Qdrant Server đang chạy bằng Docker
client = QdrantClient(url="http://localhost:6333")

# Lấy danh sách collection hiện có
collections = client.get_collections()

print("Kết nối Qdrant thành công!")
print("Danh sách collection:", collections)

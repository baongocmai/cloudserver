# from weaviate import WeaviateClient
from weaviate.connect import ConnectionParams

# client = WeaviateClient(
#     connection_params=ConnectionParams.from_url(
#         "http://localhost:8080",  # Đây là đối số đầu tiên: HTTP URL
#         grpc_port=50051           # Đây là đối số thứ hai: gRPC port
#     )
# )

# print("✅ Kết nối thành công!")
from weaviate import WeaviateClient
client = WeaviateClient(
    connection_params=ConnectionParams.from_url(
        "http://localhost:8080",  # Đây là đối số đầu tiên: HTTP URL
        grpc_port=50051           # Đây là đối số thứ hai: gRPC port
    )
)
print(dir(client))


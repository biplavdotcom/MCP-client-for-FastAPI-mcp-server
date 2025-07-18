import pika 

# def main():
connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel = connection.channel()
messages = []
def callback(ch, method, properties, body):
    messages.append(body)
    print(" [x] Received %r" % body)
channel.queue_declare(queue="signup")
channel.basic_consume(queue="signup", on_message_callback=callback, auto_ack=True)

print(" [*] Waiting for messages. To exit press CTRL+C")
channel.start_consuming()

# if __name__ == "__main__":
#     try:
#         main()
#     except KeyboardInterrupt:
#         print("\nInterrupted")
#         try:
#             sys.exit(0)
#         except SystemExit:
#             os._exit(0)
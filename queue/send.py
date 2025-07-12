import pika

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel = connection.channel()

channel.queue_declare(queue="signup")
channel.basic_publish(exchange="", routing_key="signup", body="Sanchei hununxa?")
print(" [x] Sent Message in queue")
connection.close()

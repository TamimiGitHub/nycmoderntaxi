import os
import time

from opentelemetry import trace
from opentelemetry.ext import jaeger
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchExportSpanProcessor
from opentelemetry.trace import SpanContext
from solace.messaging.messaging_service import MessagingService
from solace.messaging.resources.topic_subscription import TopicSubscription
from solace.messaging.receiver.message_receiver import MessageHandler

# Callback function to handle received messages
class MessageHandlerImpl(MessageHandler):
    def on_message(self, message: 'InboundMessage'):
        tracer = trace.get_tracer(__name__)
        trace_id = str(message.get_property("trace_id"))
        span_id = str(message.get_property("span_id"))
        print("parentSpan trace_id on receiver side:" + trace_id)
        print("parentSpan span_id on receiver side:" + span_id)

        logs_file.write("parentSpan trace_id on receiver side:" + trace_id)
        logs_file.write("parentSpan span_id on receiver side:" + span_id)

        propagated_context = SpanContext(int(trace_id), int(span_id), True)
        childSpan = tracer.start_span("RideUpdated receive", parent=propagated_context)

        topic = message.get_destination_name()
        payload_str = message.get_payload_as_string()

        print("\n" + f"REST CALLBACK: Message Received on Topic: {topic}.\n"
                     f"{int(time.time())}: {payload_str} \n")

        logs_file.write("\n" + f"REST CALLBACK: Message Received on Topic: {topic}.\n"
                     f"{int(time.time())}: {payload_str} \n\n")

        time.sleep(1)
        childSpan.end()


def direct_message_consume(messaging_service: MessagingService, topic_subscription: str):
    try:
        trace.set_tracer_provider(TracerProvider())
        jaeger_exporter = jaeger.JaegerSpanExporter(
            service_name="<Solace> REST Messaging call to Security Co",
            agent_host_name="localhost",
            agent_port=6831,
        )

        trace.get_tracer_provider().add_span_processor(
            BatchExportSpanProcessor(jaeger_exporter)
        )

        tracer = trace.get_tracer(__name__)

        topics = [TopicSubscription.of(topic_subscription)]

        # Create a direct message consumer service with the topic subscription and start it
        direct_receive_service = messaging_service.create_direct_message_receiver_builder()
        direct_receive_service = direct_receive_service.with_subscriptions(topics).build()
        direct_receive_service.start()

        # Register a callback message handler
        direct_receive_service.receive_async(MessageHandlerImpl())
        print(f"Subscribed to: {topic_subscription}")
        # Infinite loop until Keyboard interrupt is received
        try: 
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print('\nDisconnecting Messaging Service')
    finally:
        messaging_service.disconnect()
        direct_receive_service.terminate()

inboundTopic = "opentelemetry/helloworld"

broker_props = {"solace.messaging.transport.host": os.environ['SOLACE_HOST'],
                "solace.messaging.service.vpn-name": os.environ['SOLACE_VPN'],
                "solace.messaging.authentication.scheme.basic.username": os.environ['SOLACE_USERNAME'],
                "solace.messaging.authentication.scheme.basic.password": os.environ['SOLACE_PASSWORD']}

# Initialize A messaging service + Connect to the broker
messaging_service = MessagingService.builder().from_properties(broker_props).build()
messaging_service.connect_async()

# Create a directory to write to file
current_directory = os.getcwd()
logs_dir = os.path.join(current_directory, "logs")
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)
    
# Create file for logs
file_name = os.path.join(logs_dir, "REST.txt")

if os.path.exists(file_name):
    append_write = 'a' # append if already exists
else:
    append_write = 'w+' # make a new file if not
    
logs_file = open(file_name, append_write)

direct_message_consume(messaging_service, inboundTopic)

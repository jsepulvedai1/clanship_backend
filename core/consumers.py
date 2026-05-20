import channels_graphql_ws
import core.schema

class MyGraphqlWsConsumer(channels_graphql_ws.GraphqlWsConsumer):
    """
    Consumidor para manejar GraphQL sobre WebSockets.
    """
    schema = core.schema.schema

    # Opcional: Implementar autenticación aquí si es necesario
    async def on_connect(self, payload):
        # Aquí se puede validar el token JWT del payload
        pass

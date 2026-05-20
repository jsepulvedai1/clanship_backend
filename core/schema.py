import graphene
import users.schema
import chat.schema
import jobs.schema

class Query(
    users.schema.Query,
    chat.schema.Query,
    jobs.schema.Query,
    graphene.ObjectType
):
    """
    Query raíz que combina todas las aplicaciones del Marketplace.
    """
    pass

class Mutation(
    users.schema.Mutation,
    chat.schema.Mutation,
    jobs.schema.Mutation,
    graphene.ObjectType
):
    """
    Mutation raíz que combina todas las aplicaciones.
    """
    pass

class Subscription(
    chat.schema.Subscription,
    graphene.ObjectType
):
    """
    Subscription raíz para eventos en tiempo real.
    """
    pass

schema = graphene.Schema(
    query=Query, 
    mutation=Mutation,
    subscription=Subscription
)

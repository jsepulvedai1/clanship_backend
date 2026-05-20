import graphene
import users.schema
import jobs.schema

class Query(
    users.schema.Query,
    jobs.schema.Query,
    graphene.ObjectType
):
    """
    Query raíz que combina todas las aplicaciones del Marketplace.
    """
    pass

class Mutation(
    users.schema.Mutation,
    jobs.schema.Mutation,
    graphene.ObjectType
):
    """
    Mutation raíz que combina todas las aplicaciones.
    """
    pass

class Subscription(
    graphene.ObjectType
):
    """
    Subscription raíz para eventos en tiempo real.
    """
    pass

schema = graphene.Schema(
    query=Query, 
    mutation=Mutation,
)

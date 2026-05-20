import graphene

class Query(graphene.ObjectType):
    hello_trips = graphene.String(default_value="Hola desde Trips")

# class Mutation(graphene.ObjectType):
#     pass

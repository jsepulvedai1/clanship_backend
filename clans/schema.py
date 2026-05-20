import graphene

class Query(graphene.ObjectType):
    hello_clans = graphene.String(default_value="Hola desde Clans")

# class Mutation(graphene.ObjectType):
#     pass

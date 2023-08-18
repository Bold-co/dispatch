from dispatch.incident.affected_products import (
    get_teams,
    get_products,
    get_area_info,
    get_products_by_team,
    describe_products,
    get_team,
)

teams = get_teams()
print("Teams:\n", "\n".join(teams), "\n")

products = get_products()
area = get_area_info()
print("Area:\n", area, "\n")

team = get_team(teams[0])
print("Team:\n", team, "\n")

team_products = get_products_by_team(teams[0])
print("Team products:\n", team_products, "\n")

product = describe_products(teams[0], list(team_products)[0])
print("Product:\n", product, "\n")

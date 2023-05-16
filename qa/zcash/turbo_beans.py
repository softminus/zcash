# import itertools

# def generate_input_combinations(address_types, max_inputs):
#     all_combinations = []
    
#     for i in range(1, max_inputs + 1):
#         combinations = list(itertools.combinations(address_types, i))
#         all_combinations.extend(combinations)
        
#     return all_combinations

# # usage
# address_types = [
#     ["p2pkh"], # t-addr
#     ["non_ua_sapling"], # z-addr
#     ["sapling"], # UA
#     ["orchard"], # UA
#     ["sapling", "orchard"], # UA
#     ["p2pkh", "sapling"], # UA
#     ["p2pkh", "orchard"], # UA
#     ["p2pkh", "sapling", "orchard"] # UA
# ]
# max_inputs = 3  # replace with your desired max inputs
# combinations = generate_input_combinations(address_types, max_inputs)

# for combo in combinations:
#     print(combo)


import itertools
# usage
address_types = [
    ["p2pkh"], # t-addr
    ["non_ua_sapling"], # z-addr
    ["sapling"], # UA
    ["orchard"], # UA
    ["sapling", "orchard"], # UA
    ["p2pkh", "sapling"], # UA
    ["p2pkh", "orchard"], # UA
    ["p2pkh", "sapling", "orchard"] # UA
]
print(len(address_types))
combinations = list(itertools.combinations_with_replacement(address_types, 2))
for combo in combinations:
    print(combo)

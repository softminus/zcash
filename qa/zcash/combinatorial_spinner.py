# new and improved Combinatorial Spinner (not even close to working yet)

# Instead of creating a list of transactions where each transaction's input is the output of the previous transaction, we simply enumerate all possible transactions, filter out the ones we know don't work.

# This lets us cope a lot better with multiple-in / multiple-out transactions, and obviates the need to link transactions together.

# To execute the transactions, we have a first phase where we fund all the inputs, check all the inputs, and then issue all the transactions.
# Afterwards, of course, we make sure all the outputs are there.

# We then coalesce all the funds back into the original address.





from enum import Enum


address_classes = Enum("Address Classes", ["NonUA", "UA", "BareUA", "Any"])
pool_types = Enum("Pool Types", ["Transparent", "Sapling", "Orchard", "Any"])
transaction_types = Enum("Transaction Types", ["z_sendmany", "z_mergetoaddress"])
maximum_fanin_fanout = 3

class AddressType:
    def __init__(self, address_class, pool_types):
        self.address_class = address_class
        self.pool_types = pool_types
    def __str__(self):
        return f"{self.address_class.name} address, {{{str(self.pool_types)}}} protocols"
    def __repr__(self):
        return str(self)
    def __eq__(self, other):
        return self.address_class == other.address_class and self.pool_types == other.pool_types

class Transaction:
    def __init__(self, transaction_type, inputs, outputs):
        self.transaction_type = transaction_type
        self.inputs = inputs
        self.outputs = outputs
    def __str__(self):
        return f"{self.transaction_type.name} with inputs={{{self.inputs}}} and outputs {{{self.outputs}}}"
    def __repr__(self):
        return str(self)
    def __eq__(self, other):
        return self.transaction_type == other.transaction_type and self.inputs == other.inputs and self.outputs == other.outputs

    # ["sapling"], # UA
    # ["orchard"], # UA
    # ["sapling", "orchard"], # UA
    # ["p2pkh", "sapling"], # UA
    # ["p2pkh", "orchard"], # UA
    # ["p2pkh", "sapling", "orchard"] # UA

def valid_address_generator(address_class):
    valid_types = []
    if (address_class == address_classes.NonUA):
        valid_types.append(AddressType(address_classes.NonUA, pool_types.Transparent))
        valid_types.append(AddressType(address_classes.NonUA, pool_types.Sapling))
    elif (address_class == address_classes.BareUA):
        valid_types.append(AddressType(address_classes.BareUA, pool_types.Transparent))
        valid_types.append(AddressType(address_classes.BareUA, pool_types.Sapling))
        valid_types.append(AddressType(address_classes.BareUA, pool_types.Orchard))
    elif (address_class == address_classes.UA):
        valid_types.append(AddressType(address_classes.UA, [pool_types.Sapling]))
        valid_types.append(AddressType(address_classes.UA, [pool_types.Orchard]))
        valid_types.append(AddressType(address_classes.UA, [pool_types.Sapling, pool_types.Orchard]))
        valid_types.append(AddressType(address_classes.UA, [pool_types.Transparent, pool_types.Sapling]))
        valid_types.append(AddressType(address_classes.UA, [pool_types.Transparent, pool_types.Orchard]))
        valid_types.append(AddressType(address_classes.UA, [pool_types.Transparent, pool_types.Sapling, pool_types.Orchard]))
    else:
        raise Exception(f"Invalid address class: {address_class}")
    return valid_types




# so an example t-t transaction would be:
# transaction_type: z_sendmany
# inputs:
#   - address_class: non-UA
#   - pool_type: Transparent
#   - transaction_role: input
# outputs:
#   - address_class: non-UA
#   - pool_type: Transparent
#   - transaction_role: output 



# We don't yet support z_mergetoaddress with UAs as inputs

invalid_combinations = [
    Transaction(transaction_types.z_mergetoaddress, AddressType(address_classes.UA, pool_types.Any), AddressType(address_classes.Any, pool_types.Any)),
]

def create_all_transactions():
    transactions = []
    for transaction_type in transaction_types:
        for input_address_type in address_classes:
            if input_address_type == address_classes.Any:
                continue
            for output_address_type in address_classes:
                if output_address_type == address_classes.Any:
                    continue
                for input_address_types in valid_address_generator(input_address_type):
                    for output_address_types in valid_address_generator(output_address_type):
                        transactions.append(Transaction(transaction_type, input_address_types, output_address_types))
    
    return transactions

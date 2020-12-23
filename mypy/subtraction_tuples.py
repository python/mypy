def subtraction_tuples(tuple_update: tuple, tuple_delete: tuple):
    tuple_update = [i for i in tuple_update]
    tuple_delete = [i for i in tuple_delete]
    for i in range(len(tuple_delete)):
        tuple_update[i] += tuple_delete[i]
    return tuple_update
 

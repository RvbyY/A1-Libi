
def max_sum(arr, k):
    n = len(arr)
    i = 0
    result = 0

    if n <= k:
        return 84
    while i < k:
        result += arr[i]
        i += 1
    return result

# print(max_sum([5, 3, 8, 2, 0, 7, 4], 3))
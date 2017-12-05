"""REM_START
This is the mobile code for ParallelTSP. It is intended to be run on a mobile
code server and return the result.

However, it may also be imported by the local client for local/remote shared
computations. (e.g., "maxPaths()" is a useful function both remote and
locally).

Comments marked with REM_START/REM_END can be removed. Templated values can
be inserted into places appropriately marked
REM_END"""
import math

def maxPaths(n):
    """REM_START
    There are (n-1)!/2 possible unique paths between n cities. It would be n!
    but because of symmetry, it is halved.
    
    However, I don't know an algorithm for converting a scalar number to
    a path that excludes the mirrored duplicates. So, for now, we'll
    set max paths to (n-1)!
    REM_END"""
    return math.factorial(n-1)

def numToPath(n, num):
    """REM_START
    We would like to "number" each path. Ideally, we would have an algorithm
    that would take a number (num) and convert it to a unique, non-mirrored
    path. But I don't know an algorithm that can do that without actually
    iterating through paths.
    
    So, we'll just do all (n-1) factorial paths for now. For example, for
    4 cities A, B, C, D:
    
    0 = ABCDA
    1 = ABDCA
    2 = ACBDA
    3 = ...
    
    NOTE: It doesn't matter the starting city, therefore we always
    pick the first city (also why the max is (n-1)! instead of n!).
    REM_END"""
    if num >= maxPaths(n):
        return None
    # the first path is 1,2,3,4... n
    ordered_cities = list(range(n))
    path = [ordered_cities.pop(0)]
    for index in range(n-2):
        perDigit = maxPaths(n-(index+1))
        digitsThisIndex = int(num/perDigit)
        num = num - (perDigit*digitsThisIndex)
        path.append(ordered_cities[digitsThisIndex])
        ordered_cities = ordered_cities[:digitsThisIndex] + ordered_cities[digitsThisIndex+1:]
    path.append(ordered_cities[0])
    path.append(path[0])
    return path

def computeShortestPath(cities, start_num, end_num):
    shortest = None
    path = None
    for i in range(start_num, end_num+1):
        p = numToPath(len(cities), i)
        if not p: break
        prev = p[0]
        dist = 0
        for cit in p[1:]:
            dist += cities[prev][cit]
            prev = cit
        if not shortest or dist < shortest:
            shortest = dist
            path = p
    return (shortest, path)

if __name__=="__sandbox__":
    """REM_START
    This will be ignored if imported direclty. But the mobile code
    client can replace "__sandbox__" with __main__, and the variables below.
    REM_END"""
    import pickle
    cities = "__template_cities__"
    start_num = "__template_start_num__"
    end_num = "__template_end_num__"
    
    result = computeShortestPath(cities, start_num, end_num)
    print(pickle.dumps(result).hex())

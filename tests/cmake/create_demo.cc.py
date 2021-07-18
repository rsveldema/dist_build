import sys


num_loops = int(sys.argv[1])
prefix = sys.argv[2]


for i in range(0, num_loops):
    print("namespace " + prefix + "_" + str(i) + " {")
    print("    template <typename T> class Data_"+str(i)+" {")
    print("    public:")
    print("       T data;")
    if i == 0:
        print("       T& get() { return data; }")
    else:
        print("       T& get();")
        
    print("    };")
    print("}")


for i in range(0, num_loops):
    print()

    if i == 0:
        print("" + prefix + "_" + str(i) + "::Data_" + str(i) + "<int> "+prefix+"_instance_"+str(i)+" = {123};")
    else:
        j = i - 1
        print("" + prefix + "_" + str(i) + "::Data_" + str(i) + "<int> "+prefix+"_instance_"+str(i)+" = {"+prefix+"_instance_"+str(j)+".get()};")

        print("template<typename T>")
        print("T& " + prefix + "_" + str(i) + "::Data_" + str(i) + "<T>::get() { return "+prefix+"_instance_"+str(j)+".get(); }")

print("int return_value_"+prefix+"() { return "+prefix+"_instance_"+str(i) + ".get(); }")
namespace ddd_0 {
    template <typename T> class Data_0 {
    public:
       T data;
       T& get() { return data; }
    };
}
namespace ddd_1 {
    template <typename T> class Data_1 {
    public:
       T data;
       T& get();
    };
}
namespace ddd_2 {
    template <typename T> class Data_2 {
    public:
       T data;
       T& get();
    };
}

ddd_0::Data_0<int> ddd_instance_0 = {123};

ddd_1::Data_1<int> ddd_instance_1 = {ddd_instance_0.get()};
template<typename T>
T& ddd_1::Data_1<T>::get() { return ddd_instance_0.get(); }

ddd_2::Data_2<int> ddd_instance_2 = {ddd_instance_1.get()};
template<typename T>
T& ddd_2::Data_2<T>::get() { return ddd_instance_1.get(); }
int return_value_ddd() { return ddd_instance_2.get(); }

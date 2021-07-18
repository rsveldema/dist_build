namespace foo_0 {
    template <typename T> class Data_0 {
    public:
       T data;
       T& get() { return data; }
    };
}
namespace foo_1 {
    template <typename T> class Data_1 {
    public:
       T data;
       T& get();
    };
}
namespace foo_2 {
    template <typename T> class Data_2 {
    public:
       T data;
       T& get();
    };
}

foo_0::Data_0<int> foo_instance_0 = {123};

foo_1::Data_1<int> foo_instance_1 = {foo_instance_0.get()};
template<typename T>
T& foo_1::Data_1<T>::get() { return foo_instance_0.get(); }

foo_2::Data_2<int> foo_instance_2 = {foo_instance_1.get()};
template<typename T>
T& foo_2::Data_2<T>::get() { return foo_instance_1.get(); }
int return_value_foo() { return foo_instance_2.get(); }

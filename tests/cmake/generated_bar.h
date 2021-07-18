namespace bar_0 {
    template <typename T> class Data_0 {
    public:
       T data;
       T& get() { return data; }
    };
}
namespace bar_1 {
    template <typename T> class Data_1 {
    public:
       T data;
       T& get();
    };
}
namespace bar_2 {
    template <typename T> class Data_2 {
    public:
       T data;
       T& get();
    };
}

bar_0::Data_0<int> instance_0 = {123};

bar_1::Data_1<int> instance_1 = {instance_0.get()};
template<typename T>
T& bar_1::Data_1<T>::get() { return instance_0.get(); }

bar_2::Data_2<int> instance_2 = {instance_1.get()};
template<typename T>
T& bar_2::Data_2<T>::get() { return instance_1.get(); }
int return_value_bar() { return instance_2.get(); }

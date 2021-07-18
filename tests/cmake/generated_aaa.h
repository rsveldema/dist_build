namespace aaa_0 {
    template <typename T> class Data_0 {
    public:
       T data;
       T& get() { return data; }
    };
}
namespace aaa_1 {
    template <typename T> class Data_1 {
    public:
       T data;
       T& get();
    };
}
namespace aaa_2 {
    template <typename T> class Data_2 {
    public:
       T data;
       T& get();
    };
}

aaa_0::Data_0<int> aaa_instance_0 = {123};

aaa_1::Data_1<int> aaa_instance_1 = {aaa_instance_0.get()};
template<typename T>
T& aaa_1::Data_1<T>::get() { return aaa_instance_0.get(); }

aaa_2::Data_2<int> aaa_instance_2 = {aaa_instance_1.get()};
template<typename T>
T& aaa_2::Data_2<T>::get() { return aaa_instance_1.get(); }
int return_value_aaa() { return aaa_instance_2.get(); }

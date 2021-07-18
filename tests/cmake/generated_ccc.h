namespace ccc_0 {
    template <typename T> class Data_0 {
    public:
       T data;
       T& get() { return data; }
    };
}
namespace ccc_1 {
    template <typename T> class Data_1 {
    public:
       T data;
       T& get();
    };
}
namespace ccc_2 {
    template <typename T> class Data_2 {
    public:
       T data;
       T& get();
    };
}

ccc_0::Data_0<int> ccc_instance_0 = {123};

ccc_1::Data_1<int> ccc_instance_1 = {ccc_instance_0.get()};
template<typename T>
T& ccc_1::Data_1<T>::get() { return ccc_instance_0.get(); }

ccc_2::Data_2<int> ccc_instance_2 = {ccc_instance_1.get()};
template<typename T>
T& ccc_2::Data_2<T>::get() { return ccc_instance_1.get(); }
int return_value_ccc() { return ccc_instance_2.get(); }

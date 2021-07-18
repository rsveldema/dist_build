namespace bbb_0 {
    template <typename T> class Data_0 {
    public:
       T data;
       T& get() { return data; }
    };
}
namespace bbb_1 {
    template <typename T> class Data_1 {
    public:
       T data;
       T& get();
    };
}
namespace bbb_2 {
    template <typename T> class Data_2 {
    public:
       T data;
       T& get();
    };
}

bbb_0::Data_0<int> bbb_instance_0 = {123};

bbb_1::Data_1<int> bbb_instance_1 = {bbb_instance_0.get()};
template<typename T>
T& bbb_1::Data_1<T>::get() { return bbb_instance_0.get(); }

bbb_2::Data_2<int> bbb_instance_2 = {bbb_instance_1.get()};
template<typename T>
T& bbb_2::Data_2<T>::get() { return bbb_instance_1.get(); }
int return_value_bbb() { return bbb_instance_2.get(); }
